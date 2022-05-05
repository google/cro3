// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The testplan tool evaluates Starlark files to generate ChromeOS
// chromiumos.test.api.v1.HWTestPlan protos.
package main

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"math/rand"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/golang/glog"
	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	test_api_v1 "go.chromium.org/chromiumos/config/go/test/api/v1"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	luciflag "go.chromium.org/luci/common/flag"

	testplan "chromiumos/test/plan/internal"
	"chromiumos/test/plan/internal/compatibility"
	"chromiumos/test/plan/internal/coveragerules"
)

// Version is set to the CROS_GO_VERSION eclass variable at build time. See
// cros-go.eclass for details.
var Version string

// errToCode converts an error into an exit code.
func errToCode(a subcommands.Application, err error) int {
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %s\n", a.GetName(), err)
		return 1
	}

	return 0
}

// addExistingFlags adds all currently defined flags to generateRun.
//
// Some packages define flags in their init functions (e.g. glog). In order for
// these flags to be defined on a command, they need to be defined in the
// CommandRun function as well.
func (r *generateRun) addExistingFlags() {
	if !flag.Parsed() {
		panic("flag.Parse() must be called before addExistingFlags()")
	}

	flag.VisitAll(func(f *flag.Flag) {
		r.GetFlags().Var(f.Value, f.Name, f.Usage)
	})
}

var application = &subcommands.DefaultApplication{
	Name:  "testplan",
	Title: "A tool to evaluate Starlark files to generate ChromeOS chromiumos.test.api.v1.HWTestPlan protos.",
	Commands: []*subcommands.Command{
		cmdGenerate,
		cmdVersion,

		subcommands.CmdHelp,
	},
}

var cmdVersion = &subcommands.Command{
	UsageLine: "version",
	ShortDesc: "Prints the Portage package version information used to build the tool.",
	CommandRun: func() subcommands.CommandRun {
		return &versionRun{}
	},
}

type versionRun struct {
	subcommands.CommandRunBase
}

func (r *versionRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if Version == "" {
		fmt.Println("testplan version unknown, likely was not built with Portage")
		return 1
	}

	fmt.Printf("testplan version: %s\n", Version)

	return 0
}

var cmdGenerate = &subcommands.Command{
	UsageLine: "generate -plan plan1.star [-plan plan2.star] -dutattributes PATH -buildmetadata -out OUTPUT",
	ShortDesc: "generate HW test plan protos",
	LongDesc: `Generate HW test plan protos.

Evaluates Starlark files to generate HWTestPlans as newline-delimited json protos.
`,
	CommandRun: func() subcommands.CommandRun {
		r := &generateRun{}
		// TODO(b/182898188): Add more details on proto input / output for
		// Starlark files once it is implemented.
		r.Flags.Var(
			luciflag.StringSlice(&r.planPaths),
			"plan",
			"Starlark file to use. Must be specified at least once.",
		)
		r.Flags.StringVar(
			&r.dutAttributeListPath,
			"dutattributes",
			"",
			"Path to a proto file containing a DutAttributeList. Can be JSON "+
				"or binary proto.",
		)
		r.Flags.StringVar(
			&r.buildMetadataListPath,
			"buildmetadata",
			"",
			"Path to a proto file containing a SystemImage.BuildMetadataList. "+
				"Can be JSON or binary proto.",
		)
		r.Flags.StringVar(
			&r.configBundleListPath,
			"configbundlelist",
			"",
			"Path to a proto file containing a ConfigBundleList. Can be JSON or "+
				"binary proto.",
		)
		r.Flags.StringVar(
			&r.chromiumosSourceRootPath,
			"crossrcroot",
			"",
			"Path to the root of a Chromium OS source checkout. Default "+
				"versions of dutattributes, buildmetadata, configbundlelist, "+
				"and boardprioritylist in this source checkout will be used, as "+
				"a convenience to avoid specifying all these full paths. "+
				"crossrcroot is mutually exclusive with the above flags.",
		)
		r.Flags.BoolVar(
			&r.ctpV1,
			"ctpv1",
			false,
			"Output GenerateTestPlanResponse protos instead of HWTestPlans, "+
				"for backwards compatibility with CTP1. Output is still "+
				"to <out>. generatetestplanreq must be set if this flag is "+
				"true",
		)
		r.Flags.StringVar(
			&r.generateTestPlanReqPath,
			"generatetestplanreq",
			"",
			"Path to a proto file containing a GenerateTestPlanRequest. Can be"+
				"JSON or binary proto. Should be set iff ctpv1 is set.",
		)
		r.Flags.StringVar(
			&r.boardPriorityListPath,
			"boardprioritylist",
			"",
			"Path to a proto file containing a BoardPriorityList. Can be JSON"+
				"or binary proto. Should be set iff ctpv1 is set.",
		)
		r.Flags.StringVar(
			&r.out,
			"out",
			"",
			"Path to the output HWTestPlans.",
		)
		r.Flags.StringVar(
			&r.textSummaryOut,
			"textsummaryout",
			"",
			"Path to write a more easily human-readable summary of the "+
				"HWTestPlans to. If not set, no summary is written.",
		)

		r.addExistingFlags()

		return r
	},
}

type generateRun struct {
	subcommands.CommandRunBase
	planPaths                []string
	buildMetadataListPath    string
	dutAttributeListPath     string
	configBundleListPath     string
	chromiumosSourceRootPath string
	ctpV1                    bool
	generateTestPlanReqPath  string
	boardPriorityListPath    string
	out                      string
	textSummaryOut           string
}

func (r *generateRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	return errToCode(a, r.run())
}

// The v1 jsonpb package has known issues with FieldMasks:
// https://github.com/golang/protobuf/issues/745. This is fixed in the v2
// package, but as of 6/28/2021 the version of dev-go/protobuf ebuild installs
// v1.3.2 of the github.com/golang/protobuf package, which does not contain the
// MessageV2 function (required to use the v2 jsonproto package).
//
// Bumping the version of this Portage package broke dependent packages. As a
// workaround, parse out the known FieldMask messages from the jsonpb files
// we are reading.
//
// TODO(b/189223005): Fix dependent package or install multiple versions of the
// protobuf package.
var publicReplicationRegexp = regexp.MustCompile(`(?m),?\s*"publicReplication":\s*{\s*"publicFields":\s*"[^"]*"\s*}`)

// parseJsonpb parses the jsonpb in b into m.
func parseJsonpb(b []byte, m proto.Message) error {
	lenBeforeRegexp := len(b)
	b = publicReplicationRegexp.ReplaceAll(b, []byte{})

	if lenBeforeRegexp != len(b) {
		glog.V(2).Infof(
			`Removed "publicReplication" fields with regexp. Length before: %d. Length after: %d`,
			lenBeforeRegexp, len(b),
		)
	}

	unmarshaller := jsonpb.Unmarshaler{AllowUnknownFields: true}
	return unmarshaller.Unmarshal(bytes.NewReader(b), m)
}

// readBinaryOrJSONPb reads path into m, attempting to parse as both a binary
// and json encoded proto.
//
// This function is meant as a convenience so the CLI can take either json or
// binary protos as input. This function guesses at whether to attempt to parse
// as binary or json first based on path's suffix.
func readBinaryOrJSONPb(path string, m proto.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	if strings.HasSuffix(path, ".jsonpb") || strings.HasSuffix(path, ".jsonproto") {
		glog.Infof("Attempting to parse %q as jsonpb first", path)

		err = parseJsonpb(b, m)
		if err == nil {
			return nil
		}

		glog.Warningf("Parsing %q as jsonpb failed (%q), attempting to parse as binary pb", path, err)

		return proto.Unmarshal(b, m)
	}

	glog.Infof("Attempting to parse %q as binary pb first", path)

	err = proto.Unmarshal(b, m)
	if err == nil {
		return nil
	}

	glog.Warningf("Parsing %q as binarypb failed, attempting to parse as jsonpb", path)

	return parseJsonpb(b, m)
}

// readTextpb reads the textpb at path into m.
func readTextpb(path string, m proto.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	return proto.UnmarshalText(string(b), m)
}

// writePlans writes a newline-delimited json file containing plans to outPath.
func writePlans(plans []*test_api_v1.HWTestPlan, outPath, textSummaryOutPath string) error {
	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()

	marshaler := jsonpb.Marshaler{}
	allRules := []*testpb.CoverageRule{}

	for _, plan := range plans {
		jsonString, err := marshaler.MarshalToString(plan)
		if err != nil {
			return err
		}

		jsonString += "\n"

		if _, err = outFile.Write([]byte(jsonString)); err != nil {
			return err
		}

		allRules = append(allRules, plan.GetCoverageRules()...)
	}

	if textSummaryOutPath != "" {
		glog.Infof("Writing text summary file to %s", textSummaryOutPath)

		textSummaryOutFile, err := os.Create(textSummaryOutPath)
		if err != nil {
			return err
		}
		defer textSummaryOutFile.Close()

		if err = coveragerules.WriteTextSummary(textSummaryOutFile, allRules); err != nil {
			return err
		}
	}

	return nil
}

// validateFlags checks valid flags are passed to generate, e.g. all required
// flags are set.
//
// If r.chromiumosSourceRootPath is set, other flags (e.g.
// r.dutAttributeListPath) are updated to default values relative to the source
// root.
func (r *generateRun) validateFlags() error {
	if len(r.planPaths) == 0 {
		return errors.New("at least one -plan is required")
	}

	if r.chromiumosSourceRootPath == "" {
		if r.dutAttributeListPath == "" {
			return errors.New("-dutattributes is required if -crossrcroot is not set")
		}

		if r.buildMetadataListPath == "" {
			return errors.New("-buildmetadata is required if -crossrcroot is not set")
		}

		if r.configBundleListPath == "" {
			return errors.New("-configbundlelist is required if -crossrcroot is not set")
		}

		if r.ctpV1 && r.boardPriorityListPath == "" {
			return errors.New("-boardprioritylist or -crossrcroot must be set if -ctpv1 is set")
		}
	} else {
		if r.dutAttributeListPath != "" || r.buildMetadataListPath != "" || r.configBundleListPath != "" || r.boardPriorityListPath != "" {
			return errors.New("-dutattributes, -buildmetadata, -configbundlelist, and -boardprioritylist cannot be set if -crossrcroot is set")
		}

		glog.V(2).Infof("crossrcroot set to %q, updating dutattributes, buildmetadata, and configbundlelist", r.chromiumosSourceRootPath)
		r.dutAttributeListPath = filepath.Join(r.chromiumosSourceRootPath, "src", "config", "generated", "dut_attributes.jsonproto")
		r.buildMetadataListPath = filepath.Join(r.chromiumosSourceRootPath, "src", "config-internal", "build", "generated", "build_metadata.jsonproto")
		r.configBundleListPath = filepath.Join(r.chromiumosSourceRootPath, "src", "config-internal", "hw_design", "generated", "configs.jsonproto")

		if r.ctpV1 {
			glog.V(2).Infof("crossrcroot set to %q, updating boardprioritylist", r.chromiumosSourceRootPath)
			r.boardPriorityListPath = filepath.Join(r.chromiumosSourceRootPath, "src", "config-internal", "board_config", "generated", "board_priority.binaryproto")
		}
	}

	if r.out == "" {
		return errors.New("-out is required")
	}

	if r.ctpV1 != (r.generateTestPlanReqPath != "") {
		return errors.New("-generatetestplanreq must be set iff -out is set.")
	}

	if !r.ctpV1 && r.boardPriorityListPath != "" {
		return errors.New("-boardprioritylist cannot be set if -ctpv1 is not set")
	}

	return nil
}

// run is the actual implementation of the generate command.
func (r *generateRun) run() error {
	ctx := context.Background()

	if err := r.validateFlags(); err != nil {
		return err
	}

	buildMetadataList := &buildpb.SystemImage_BuildMetadataList{}
	if err := readBinaryOrJSONPb(r.buildMetadataListPath, buildMetadataList); err != nil {
		return err
	}

	glog.Infof("Read %d SystemImage.Metadata from %s", len(buildMetadataList.Values), r.buildMetadataListPath)

	for _, buildMetadata := range buildMetadataList.Values {
		glog.V(2).Infof("Read BuildMetadata: %s", buildMetadata)
	}

	dutAttributeList := &testpb.DutAttributeList{}
	if err := readBinaryOrJSONPb(r.dutAttributeListPath, dutAttributeList); err != nil {
		return err
	}

	glog.Infof("Read %d DutAttributes from %s", len(dutAttributeList.DutAttributes), r.dutAttributeListPath)

	for _, dutAttribute := range dutAttributeList.DutAttributes {
		glog.V(2).Infof("Read DutAttribute: %s", dutAttribute)
	}

	glog.Infof("Starting read of ConfigBundleList from %s", r.configBundleListPath)

	configBundleList := &payload.ConfigBundleList{}
	if err := readBinaryOrJSONPb(r.configBundleListPath, configBundleList); err != nil {
		return err
	}

	glog.Infof("Read %d ConfigBundles from %s", len(configBundleList.Values), r.configBundleListPath)

	hwTestPlans, err := testplan.Generate(
		ctx, r.planPaths, buildMetadataList, dutAttributeList, configBundleList,
	)
	if err != nil {
		return err
	}

	if r.ctpV1 {
		glog.Infof(
			"Outputting GenerateTestPlanRequest to %s instead of HWTestPlan, for backwards compatibility with CTPV1",
			r.out,
		)

		generateTestPlanReq := &testplans.GenerateTestPlanRequest{}
		if err := readBinaryOrJSONPb(r.generateTestPlanReqPath, generateTestPlanReq); err != nil {
			return err
		}

		boardPriorityList := &testplans.BoardPriorityList{}
		if err := readBinaryOrJSONPb(r.boardPriorityListPath, boardPriorityList); err != nil {
			return err
		}

		resp, err := compatibility.ToCTP1(
			rand.New(rand.NewSource(time.Now().Unix())),
			hwTestPlans, generateTestPlanReq, dutAttributeList, boardPriorityList,
		)
		if err != nil {
			return err
		}

		outFile, err := os.Create(r.out)
		defer outFile.Close()

		respBytes, err := proto.Marshal(resp)
		if err != nil {
			return err
		}

		if _, err := outFile.Write(respBytes); err != nil {
			return err
		}

		return nil
	}

	glog.Infof("Generated %d CoverageRules, writing to %s", len(hwTestPlans), r.out)

	return writePlans(hwTestPlans, r.out, r.textSummaryOut)
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
