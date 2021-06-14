// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package coveragerules converts a merged SourceTestPlan into CoverageRules.
package coveragerules

import (
	"fmt"
	"io"
	"reflect"
	"sort"
	"strings"
	"text/tabwriter"

	"github.com/golang/glog"
	configpb "go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
	"go.chromium.org/luci/common/data/stringset"
)

var (
	buildTargetAttributeID = &testpb.DutAttribute_Id{Value: "system_build_target"}
	fingerprintAttributeID = &testpb.DutAttribute_Id{Value: "fingerprint_location"}
)

func getSingleDutCriterionOrPanic(rule *testpb.CoverageRule) *testpb.DutCriterion {
	if len(rule.DutCriteria) != 1 {
		panic(fmt.Sprintf("expected exactly one DutCriterion, got rule %s", rule))
	}

	return rule.DutCriteria[0]
}

// expandCoverageRules joins newRules to curRules, by intersecting DutCriteria.
//
// For each combination of CoverageRules (a, b), where a is in curRules, and b
// is in newRules, a new CoverageRule is added to the result, with
// DutCriterion.Values that are the intersection of a.DutCriteria[0].Values and
// b.DutCriteria[0].Values
//
// It is assumed each CoverageRule has exactly one DutCriterion (this function
// panics if this is not true).
//
// All CoverageRules in either newRules or curRules that don't have any
// intersection of DutCriterion.Values are added to the result as is.
//
// For example, if curRules is
// {
// 	  {
// 		  Name: "A", DutCriteria: {{Values:"1"}},
// 	  },
// 	  {
// 		  Name: "B", DutCriteria: {{Values:"2"}},
// 	  },
// }
//
// and newRules is
//
// {
// 	  {
// 		  Name: "C", DutCriteria: {{Values:"1", "3"}},
// 	  },
// 	  {
// 		  Name: "D", DutCriteria: {{Values:"4"}},
// 	  },
// }
//
// the result is
//
// {
// 	  {
// 		  Name: "A_C", DutCriteria: {{Values:"1"}},
// 	  },
// 	  {
// 		  Name: "B", DutCriteria: {{Values:"2"}},
// 	  },
// 	  {
// 		  Name: "D", DutCriteria: {{Values:"4"}},
// 	  },
// }
//
// because "A" and "C" are joined, "B" and "D" are passed through as is.
//
// If curRules is empty, newRules is returned (this function is intended to
// be called multiple times to build up a result, curRules is empty in the
// first call).
func expandCoverageRules(curRules, newRules []*testpb.CoverageRule) []*testpb.CoverageRule {
	for _, rule := range newRules {
		glog.V(2).Infof("Joining CoverageRule %s", rule)
	}

	if len(curRules) == 0 {
		return newRules
	}

	// Make a map from name to CoverageRule for all CoverageRules in curRules
	// and newRules. If a CoverageRule is involved in an intersection, it is
	// removed from unjoinedRules.
	unjoinedRules := make(map[string]*testpb.CoverageRule)
	for _, rule := range append(curRules, newRules...) {
		unjoinedRules[rule.Name] = rule
	}

	expandedRules := make([]*testpb.CoverageRule, 0)

	for _, cur := range curRules {
		for _, new := range newRules {
			curDC := getSingleDutCriterionOrPanic(cur)
			newDC := getSingleDutCriterionOrPanic(new)

			if curDC.AttributeId.Value != newDC.AttributeId.Value {
				continue
			}

			valueIntersection := stringset.NewFromSlice(
				curDC.Values...,
			).Intersect(
				stringset.NewFromSlice(newDC.Values...),
			)

			if len(valueIntersection) > 0 {
				delete(unjoinedRules, cur.Name)
				delete(unjoinedRules, new.Name)

				expandedRules = append(expandedRules, &testpb.CoverageRule{
					Name: fmt.Sprintf("%s_%s", cur.Name, new.Name),
					DutCriteria: []*testpb.DutCriterion{
						{
							AttributeId: curDC.AttributeId,
							Values:      valueIntersection.ToSlice(),
						},
					},
					TestSuites: cur.TestSuites,
				})
			}
		}
	}

	// Return all unjoined rules as is.
	for _, rule := range unjoinedRules {
		expandedRules = append(expandedRules, rule)
	}

	return expandedRules
}

// buildTargetCoverageRules groups BuildTarget overlay names in
// buildSummaryList and returns one CoverageRule per group.
//
// For each BuildSummary in buildSummaryList, keyFn is called to get a string
// key. All overlay names that share the same string key are used to create a
// CoverageRule.
//
// nameFn converts a key returned by keyFn to a Name for the CoverageRule.
//
// For example, to create one CoverageRule for each kernel version, keyFn should
// return the kernel version found in a BuildSummary, and nameFn could return
// the string "kernel:<key>".
//
// If keyFn returns the empty string, that BuildSummary is skipped.
func buildTargetCoverageRules(
	keyFn func(*buildpb.SystemImage_BuildSummary) string,
	nameFn func(string) string,
	buildSummaryList *buildpb.SystemImage_BuildSummaryList,
	sourceTestPlan *plan.SourceTestPlan,
) []*testpb.CoverageRule {
	keyToBuildTargets := make(map[string][]string)

	for _, value := range buildSummaryList.GetValues() {
		key := keyFn(value)
		if key == "" {
			continue
		}

		if _, found := keyToBuildTargets[key]; !found {
			keyToBuildTargets[key] = []string{}
		}

		keyToBuildTargets[key] = append(
			keyToBuildTargets[key], value.GetBuildTarget().GetPortageBuildTarget().GetOverlayName(),
		)
	}

	coverageRules := make([]*testpb.CoverageRule, 0, len(keyToBuildTargets))
	for key, buildTargets := range keyToBuildTargets {
		coverageRules = append(coverageRules, &testpb.CoverageRule{
			Name: nameFn(key),
			TestSuites: []*testpb.TestSuite{
				{
					TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
						Tags:        sourceTestPlan.TestTags,
						TagExcludes: sourceTestPlan.TestTagExcludes,
					},
				},
			},
			DutCriteria: []*testpb.DutCriterion{
				{
					AttributeId: buildTargetAttributeID,
					Values:      buildTargets,
				},
			},
		})
	}

	return coverageRules
}

// kernelCoverageRules returns CoverageRules requiring each kernel version.
func kernelCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, buildSummaryList *buildpb.SystemImage_BuildSummaryList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildSummary *buildpb.SystemImage_BuildSummary) string {
			version := buildSummary.GetKernel().GetVersion()
			// Some BuildSummaries have a kernel version set to "0.0", skip
			// these.
			if version == "0.0" {
				glog.V(1).Infof("BuildSummary with kernel version \"0.0\", skipping: %q", buildSummary)
				return ""
			}

			return version
		},
		func(key string) string {
			return fmt.Sprintf("kernel:%s", key)
		},
		buildSummaryList,
		sourceTestPlan,
	)
}

// socCoverageRules returns CoverageRules requiring each SoC family.
func socCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, buildSummaryList *buildpb.SystemImage_BuildSummaryList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildSummary *buildpb.SystemImage_BuildSummary) string {
			return buildSummary.GetChipset().GetOverlay()
		},
		func(key string) string {
			return fmt.Sprintf("soc:%s", key)
		},
		buildSummaryList,
		sourceTestPlan,
	)
}

// arcCoverageRules returns a CoverageRule requiring each ARC version.
func arcCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, buildSummaryList *buildpb.SystemImage_BuildSummaryList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildSummary *buildpb.SystemImage_BuildSummary) string {
			return buildSummary.GetArc().GetVersion()
		},
		func(key string) string {
			return fmt.Sprintf("arc:%s", key)
		},
		buildSummaryList,
		sourceTestPlan,
	)
}

// fingerprintCoverageRule returns a CoverageRule requiring a fingerprint
// sensor.
func fingerprintCoverageRule(sourceTestPlan *plan.SourceTestPlan) *testpb.CoverageRule {
	presentEnums := []string{}

	for name, value := range configpb.HardwareFeatures_Fingerprint_Location_value {
		if value != int32(configpb.HardwareFeatures_Fingerprint_LOCATION_UNKNOWN) &&
			value != int32(configpb.HardwareFeatures_Fingerprint_NOT_PRESENT) {
			presentEnums = append(presentEnums, name)
		}
	}

	return &testpb.CoverageRule{
		Name: "fp:present",
		TestSuites: []*testpb.TestSuite{
			{
				TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
					Tags:        sourceTestPlan.TestTags,
					TagExcludes: sourceTestPlan.TestTagExcludes,
				},
			},
		},
		DutCriteria: []*testpb.DutCriterion{
			{
				AttributeId: fingerprintAttributeID,
				Values:      presentEnums,
			},
		},
	}
}

// checkDutAttributesValid checks that the ids of all attributes in rules are in
// dutAttributeList.
func checkDutAttributesValid(rules []*testpb.CoverageRule, dutAttributeList *testpb.DutAttributeList) error {
	validAttributes := stringset.New(0)

	for _, dutAttribute := range dutAttributeList.DutAttributes {
		validAttributes.Add(dutAttribute.Id.Value)
	}

	invalidAttributes := []string{}

	for _, rule := range rules {
		for _, criterion := range rule.DutCriteria {
			if !validAttributes.Has(criterion.AttributeId.Value) {
				invalidAttributes = append(invalidAttributes, criterion.AttributeId.Value)
			}
		}
	}

	if len(invalidAttributes) > 0 {
		return fmt.Errorf("CoverageRule contains invalid DutAttributes: %q", invalidAttributes)
	}

	return nil
}

// Generate computes a list of CoverageRules, based on sourceTestPlan and
// buildSummaryList.
func Generate(
	sourceTestPlan *plan.SourceTestPlan,
	buildSummaryList *buildpb.SystemImage_BuildSummaryList,
	dutAttributeList *testpb.DutAttributeList,
) ([]*testpb.CoverageRule, error) {
	coverageRules := []*testpb.CoverageRule{}

	// For each requirement set in sourceTestPlan, switch on the type of the
	// requirement and call the corresponding <requirement>Outputs function.
	//
	// Return an error if no requirements are set, or a requirement is
	// unimplemented.

	hasRequirement := false

	reqs := sourceTestPlan.Requirements
	if reqs != nil {
		// As of 6/9/2021, the dev-go/protobuf ebuild installs v1.3.2 of the
		// github.com/golang/protobuf package, which does not contain the
		// MessageReflect function.
		//
		// Bumping the version of this package broke dependent packages. Use the
		// standard reflect package instead.
		//
		// TODO(b/189223005): Fix dependent package or install multiple versions
		// of the protobuf package.
		reqsValue := reflect.ValueOf(*reqs)

		for i := 0; i < reqsValue.NumField(); i++ {
			fieldValue := reqsValue.Field(i)

			// All Requirements should be messages, so pointers to structs in
			// the generated Go. Use IsZero to check if they are set (even if
			// no fields within them are set).
			if fieldValue.Kind() != reflect.Ptr || fieldValue.IsZero() {
				continue
			}

			hasRequirement = true

			// Get the type name of the field, removing "*plan.", for use in log
			// and error messages.
			typeName := strings.ReplaceAll(fieldValue.Type().String(), "*plan.", "")

			switch fieldValue.Interface().(type) {
			case *plan.SourceTestPlan_Requirements_ArcVersions:
				coverageRules = expandCoverageRules(coverageRules, arcCoverageRules(sourceTestPlan, buildSummaryList))

			case *plan.SourceTestPlan_Requirements_KernelVersions:
				coverageRules = expandCoverageRules(coverageRules, kernelCoverageRules(sourceTestPlan, buildSummaryList))

			case *plan.SourceTestPlan_Requirements_SocFamilies:
				coverageRules = expandCoverageRules(coverageRules, socCoverageRules(sourceTestPlan, buildSummaryList))

			case *plan.SourceTestPlan_Requirements_Fingerprint:
				coverageRules = expandCoverageRules(
					coverageRules, []*testpb.CoverageRule{fingerprintCoverageRule(sourceTestPlan)},
				)

			default:
				return nil, fmt.Errorf("unimplemented requirement %q", typeName)
			}

			glog.V(1).Infof("Added CoverageRules for %q, now have %d CoverageRules", typeName, len(coverageRules))
		}
	}

	if !hasRequirement {
		return nil, fmt.Errorf("at least one requirement must be set in SourceTestPlan: %v", sourceTestPlan)
	}

	if err := checkDutAttributesValid(coverageRules, dutAttributeList); err != nil {
		return nil, err
	}

	return coverageRules, nil
}

// WriteTextSummary writes a more easily human-readable summary of coverageRules
// to w.
//
// The summary has space-separated columns for rule name, DutCriteria id, and
// DutCriteria values. Each rule name and DutCriterion id gets it's own row,
// with valid DutCriterion values separated by "|" in the row. For example:
//
// name                  attribute_id          attribute_values
// rule1                 attridA               attrv2|verylongdutattributevalue
// rule1                 longdutattributeid    attrv70
// rule2withalongname    attridB               attrv3
func WriteTextSummary(w io.Writer, coverageRules []*testpb.CoverageRule) error {
	// Constants to control tabwriter behavior. Ideally tabwriter would use an
	// options struct so the name for each parameter was clear in the code.
	// Since we don't control the tabwriter package, just use named constants
	// instead.
	const (
		minwidth = 0
		tabwidth = 8
		padding  = 4
		padchar  = ' '
		flags    = 0
	)

	tabWriter := tabwriter.NewWriter(w, minwidth, tabwidth, padding, padchar, flags)

	if _, err := fmt.Fprintln(tabWriter, "name\tattribute_id\tattribute_values"); err != nil {
		return err
	}

	for _, rule := range coverageRules {
		for _, criterion := range rule.DutCriteria {
			sort.Strings(criterion.Values)
			valuesString := strings.Join(criterion.Values, "|")

			if _, err := fmt.Fprintf(
				tabWriter, "%s\t%s\t%s\n", rule.Name, criterion.AttributeId.Value, valuesString,
			); err != nil {
				return err
			}
		}
	}

	return tabWriter.Flush()
}
