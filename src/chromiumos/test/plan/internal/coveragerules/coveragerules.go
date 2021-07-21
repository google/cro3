// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package coveragerules converts a merged SourceTestPlan into CoverageRules.
package coveragerules

import (
	"fmt"
	"io"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"text/tabwriter"

	"github.com/golang/glog"
	configpb "go.chromium.org/chromiumos/config/go/api"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
	"go.chromium.org/luci/common/data/stringset"
)

var (
	buildTargetAttributeID            = &testpb.DutAttribute_Id{Value: "system_build_target"}
	fingerprintAttributeID            = &testpb.DutAttribute_Id{Value: "fingerprint_location"}
	designIDAttributeID               = &testpb.DutAttribute_Id{Value: "design_id"}
	firmwareROMajorVersionAttributeID = &testpb.DutAttribute_Id{Value: "firmware_ro_major_version"}
	firmwareROMinorVersionAttributeID = &testpb.DutAttribute_Id{Value: "firmware_ro_minor_version"}
	firmwareROPatchVersionAttributeID = &testpb.DutAttribute_Id{Value: "firmware_ro_patch_version"}
)

// sortDutCriteriaOrPanic sorts rule.DutCriteria by AttributeId, panicing if
// rule has an empty DutCriteria.
func sortDutCriteriaOrPanic(rule *testpb.CoverageRule) {
	if len(rule.DutCriteria) == 0 {
		panic(fmt.Sprintf("expected at least one DutCriterion, got rule %s", rule))
	}

	sort.Slice(rule.DutCriteria, func(i, j int) bool {
		return rule.DutCriteria[i].AttributeId.Value < rule.DutCriteria[j].AttributeId.Value
	})
}

// expandCoverageRules joins newRules to curRules, by intersecting DutCriteria.
//
// For each combination of CoverageRules (a, b), where a is in curRules, and b
// is in newRules, a new CoverageRule is added to the result, with
// DutCriterion.Values that are the intersection of a.DutCriteria[i].Values and
// b.DutCriteria[i].Values.
//
// If a and b do not have the exact same set of DutAttribute.Ids, they are not
// joined.
//
// It is assumed each CoverageRule has at least one DutCriterion (this function
// panics if this is not true).
//
// All CoverageRules in either newRules or curRules that don't have any
// intersection of DutCriterion.Values are added to the result as is.
//
// For example, if curRules is
// {
//    {
//        Name: "A",
//        DutCriteria: {
//          {AttributeId: {Value: "Attr1"}, Values:{"1", "2"}}
//          {AttributeId: {Value: "Attr2"}, Values:{"3", "4"}}
//        },
//    },
//    {
// 		  Name: "B", DutCriteria: {{AttributeId: {Value: "Attr1"}, Values:"5"}},
// 	  },
// }
//
// and newRules is
//
// {
//    {
//        Name: "C",
//        DutCriteria: {
//          {AttributeId: {Value: "Attr1"}, Values:{"2", "5"}}
//          {AttributeId: {Value: "Attr2"}, Values:{"3", "5"}}
//        },
//    },
//    {
//        Name: "D", DutCriteria: {{AttributeId: {Value: "Attr3"}, Values:"4"}},
//    },
// }
//
// the result is
//
// {
//    {
//        Name: "A_C",
//        DutCriteria: {
//          {AttributeId: {Value: "Attr1"}, Values:{"2"}}
//          {AttributeId: {Value: "Attr2"}, Values:{"3"}}
//        },
//    },
//    {
//        Name: "B", DutCriteria: {{{AttributeId: {Value: "Attr1"}, Values:"2"}},
//    },
//    {
//        Name: "D", DutCriteria: {{AttributeId: {Value: "Attr3"}, Values:"4"}},
//    },
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
	NewRulesLoop:
		for _, new := range newRules {
			if len(cur.DutCriteria) != len(new.DutCriteria) {
				glog.V(2).Infof("Rules %s and %s have a different number of DutCriteria, not joining", cur.Name, new.Name)
				continue NewRulesLoop
			}

			sortDutCriteriaOrPanic(cur)
			sortDutCriteriaOrPanic(new)

			var joinedCriteria []*testpb.DutCriterion

			for i := range cur.DutCriteria {
				// DutCriteria were sorted above, so if cur and new have the
				// same set of DutAttribute.Ids, curCriterion and newCriterion
				// should have the same DutAttribute.Id.
				curCriterion := cur.DutCriteria[i]
				newCriterion := new.DutCriteria[i]

				if curCriterion.AttributeId.Value != newCriterion.AttributeId.Value {
					glog.V(2).Infof("Rules %s and %s have a different types of DutCriteria, not joining", cur.Name, new.Name)
					continue NewRulesLoop
				}

				valueIntersection := stringset.NewFromSlice(
					curCriterion.Values...,
				).Intersect(
					stringset.NewFromSlice(newCriterion.Values...),
				)

				if len(valueIntersection) == 0 {
					glog.V(2).Infof(
						"Rules %s and %s have a no intersection for Attribute %s, not joining",
						cur.Name, new.Name, curCriterion.AttributeId,
					)
					continue NewRulesLoop
				}

				joinedCriteria = append(joinedCriteria, &testpb.DutCriterion{
					AttributeId: curCriterion.AttributeId,
					Values:      valueIntersection.ToSortedSlice(),
				})
			}

			if len(joinedCriteria) != len(cur.DutCriteria) {
				panic(
					fmt.Sprintf(
						"expected joined criteria to have the same length as cur criteria, got %d and %d",
						len(joinedCriteria), len(cur.DutCriteria),
					),
				)
			}

			delete(unjoinedRules, cur.Name)
			delete(unjoinedRules, new.Name)

			expandedRules = append(expandedRules, &testpb.CoverageRule{
				Name:        fmt.Sprintf("%s_%s", cur.Name, new.Name),
				DutCriteria: joinedCriteria,
				TestSuites:  cur.TestSuites,
			})
		}
	}

	// Return all unjoined rules as is.
	for _, rule := range unjoinedRules {
		expandedRules = append(expandedRules, rule)
	}

	return expandedRules
}

// buildTargetCoverageRules groups BuildTarget overlay names in
// SystemImage.Metadata and returns one CoverageRule per group.
//
// For each entry in MetadataList, keyFn is called to get a string
// key. All overlay names that share the same string key are used to create a
// CoverageRule.
//
// nameFn converts a key returned by keyFn to a Name for the CoverageRule.
//
// For example, to create one CoverageRule for each kernel version, keyFn should
// return the kernel version found in a BuildMetadata, and nameFn could return
// the string "kernel:<key>".
//
// If keyFn returns the empty string, that entry is skipped.
func buildTargetCoverageRules(
	keyFn func(*buildpb.SystemImage_BuildMetadata) string,
	nameFn func(string) string,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	sourceTestPlan *plan.SourceTestPlan,
) []*testpb.CoverageRule {
	keyToBuildTargets := make(map[string][]string)

	for _, value := range buildMetadataList.GetValues() {
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
					Spec: &testpb.TestSuite_TestCaseTagCriteria_{
						TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
							Tags:        sourceTestPlan.TestTags,
							TagExcludes: sourceTestPlan.TestTagExcludes,
						},
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
	sourceTestPlan *plan.SourceTestPlan, buildMetadataList *buildpb.SystemImage_BuildMetadataList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildMetadata *buildpb.SystemImage_BuildMetadata) string {
			version := buildMetadata.GetPackageSummary().GetKernel().GetVersion()
			// Some BuildSummaries have a kernel version set to "0.0", skip
			// these.
			if version == "0.0" {
				glog.V(1).Infof("BuildMetadata with kernel version \"0.0\", skipping: %q", buildMetadata)
				return ""
			}

			return version
		},
		func(key string) string {
			return fmt.Sprintf("kernel:%s", key)
		},
		buildMetadataList,
		sourceTestPlan,
	)
}

// socCoverageRules returns CoverageRules requiring each SoC family.
func socCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, buildMetadataList *buildpb.SystemImage_BuildMetadataList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildMetadata *buildpb.SystemImage_BuildMetadata) string {
			return buildMetadata.GetPackageSummary().GetChipset().GetOverlay()
		},
		func(key string) string {
			return fmt.Sprintf("soc:%s", key)
		},
		buildMetadataList,
		sourceTestPlan,
	)
}

// arcCoverageRules returns a CoverageRule requiring each ARC version.
func arcCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, buildMetadataList *buildpb.SystemImage_BuildMetadataList,
) []*testpb.CoverageRule {
	return buildTargetCoverageRules(
		func(buildMetadata *buildpb.SystemImage_BuildMetadata) string {
			return buildMetadata.GetPackageSummary().GetArc().GetVersion()
		},
		func(key string) string {
			return fmt.Sprintf("arc:%s", key)
		},
		buildMetadataList,
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
				Spec: &testpb.TestSuite_TestCaseTagCriteria_{
					TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
						Tags:        sourceTestPlan.TestTags,
						TagExcludes: sourceTestPlan.TestTagExcludes,
					},
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

// parseInt32OrPanic parses s into an int32.
//
// Assumes s is in base10. This function should only be used in cases where s is
// known to be an int, e.g. if it was a regexp match for digits. Otherwise, use
// strconv and handle the error appropriately.
func parseInt32OrPanic(s string) int32 {
	i, err := strconv.ParseInt(s, 10, 32)
	if err != nil {
		panic(fmt.Sprintf("unable to parse %q: %v", s, err))
	}

	return int32(i)
}

var fwImageNameRegexp = regexp.MustCompile(`bcs://[^.]+\.(\d+)\.(\d+)\.(\d+)\.tbz2`)

// firmwareROCoverageRules returns CoverageRules requiring firmware tests to
// be run on each Design in FirmwareRoVersions.ProgramToMilestone.
func firmwareROCoverageRules(
	sourceTestPlan *plan.SourceTestPlan, flatConfigWrapper *flatConfigWrapper,
) ([]*testpb.CoverageRule, error) {
	coverageRules := make([]*testpb.CoverageRule, 0)

	programToMilestone := sourceTestPlan.GetRequirements().GetFirmwareRoVersions().GetProgramToMilestone()
	if len(programToMilestone) == 0 {
		return nil, fmt.Errorf("programToMilestone must be set in SourceTestPlan: %s", sourceTestPlan)
	}

	for program := range programToMilestone {
		configs, ok := flatConfigWrapper.getProgramConfigs(program)
		if !ok {
			return nil, fmt.Errorf("configs for program %q not found", program)
		}

		designIDToROVersion := make(map[string]*buildpb.Version)

		for _, config := range configs {
			designID := config.GetHwDesign().GetId().GetValue()
			roPayload := config.GetSwConfig().GetFirmware().GetMainRoPayload()
			version := roPayload.GetVersion()

			if version == nil {
				glog.V(1).Infof(
					"No RO firmware version info found for design %q, config %q, attempting to parse firmwareImageName",
					designID,
					config.GetHwDesignConfig().GetId().GetValue(),
				)

				matches := fwImageNameRegexp.FindStringSubmatch(roPayload.GetFirmwareImageName())
				if matches == nil {
					glog.V(1).Infof(
						"Could not parse firmware version info from image name %q, skipping",
						roPayload.GetFirmwareImageName(),
					)

					continue
				}

				version = &buildpb.Version{
					Major: parseInt32OrPanic(matches[1]),
					Minor: parseInt32OrPanic(matches[2]),
					Patch: parseInt32OrPanic(matches[3]),
				}
			}

			// If the Design doesn't have a Version yet, assign one. Otherwise,
			// check the Version is the same across all configs for a given
			// Design.
			if storedVersion, ok := designIDToROVersion[designID]; !ok {
				designIDToROVersion[designID] = version
			} else if !reflect.DeepEqual(storedVersion, version) {
				return nil, fmt.Errorf(
					"conflicting firmware RO versions found for design %q: %s, %s", designID, version, storedVersion,
				)
			}
		}

		if len(designIDToROVersion) == 0 {
			return nil, fmt.Errorf("no RO firmware version info found for program %q", program)
		}

		for designID, version := range designIDToROVersion {
			coverageRules = append(coverageRules, &testpb.CoverageRule{
				Name: fmt.Sprintf("%s_faft", designID),
				TestSuites: []*testpb.TestSuite{
					{
						Name: "faft_smoke",
						Spec: &testpb.TestSuite_TestCaseTagCriteria_{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"suite:faft_smoke"},
							},
						},
					},
					{
						Name: "faft_bios",
						Spec: &testpb.TestSuite_TestCaseTagCriteria_{
							TestCaseTagCriteria: &testpb.TestSuite_TestCaseTagCriteria{
								Tags: []string{"suite:faft_bios"},
							},
						},
					},
				},
				DutCriteria: []*testpb.DutCriterion{
					{
						AttributeId: designIDAttributeID,
						Values:      []string{designID},
					},
					{
						AttributeId: firmwareROMajorVersionAttributeID,
						Values:      []string{strconv.FormatInt(int64(version.Major), 10)},
					},
					{
						AttributeId: firmwareROMinorVersionAttributeID,
						Values:      []string{strconv.FormatInt(int64(version.Minor), 10)},
					},
					{
						AttributeId: firmwareROPatchVersionAttributeID,
						Values:      []string{strconv.FormatInt(int64(version.Patch), 10)},
					},
				},
			})
		}
	}

	return coverageRules, nil
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
// buildMetadataList.
//
// The returned CoverageRules are sorted by Name.
func Generate(
	sourceTestPlan *plan.SourceTestPlan,
	buildMetadataList *buildpb.SystemImage_BuildMetadataList,
	dutAttributeList *testpb.DutAttributeList,
	flatConfigList *payload.FlatConfigList,
) ([]*testpb.CoverageRule, error) {
	coverageRules := []*testpb.CoverageRule{}

	flatConfigWrapper := newFlatConfigWrapper(flatConfigList)

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
				coverageRules = expandCoverageRules(coverageRules, arcCoverageRules(sourceTestPlan, buildMetadataList))

			case *plan.SourceTestPlan_Requirements_KernelVersions:
				coverageRules = expandCoverageRules(coverageRules, kernelCoverageRules(sourceTestPlan, buildMetadataList))

			case *plan.SourceTestPlan_Requirements_SocFamilies:
				coverageRules = expandCoverageRules(coverageRules, socCoverageRules(sourceTestPlan, buildMetadataList))

			case *plan.SourceTestPlan_Requirements_Fingerprint:
				coverageRules = expandCoverageRules(
					coverageRules, []*testpb.CoverageRule{fingerprintCoverageRule(sourceTestPlan)},
				)

			case *plan.SourceTestPlan_Requirements_FirmwareROVersions:
				newRules, err := firmwareROCoverageRules(sourceTestPlan, flatConfigWrapper)
				if err != nil {
					return nil, err
				}

				coverageRules = expandCoverageRules(coverageRules, newRules)
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

	sort.SliceStable(coverageRules, func(i, j int) bool {
		return coverageRules[i].Name < coverageRules[j].Name
	})

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
