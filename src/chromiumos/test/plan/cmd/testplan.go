// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The testplan tool evaluates Starlark files to generate ChromeOS
// chromiumos.test.api.v1.HWTestPlan protos.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"time"

	"github.com/golang/glog"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/payload"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/infra/proto/go/testplans"
	luciflag "go.chromium.org/luci/common/flag"
	"google.golang.org/protobuf/encoding/protojson"

	testplan "chromiumos/test/plan/internal"
	"chromiumos/test/plan/internal/compatibility"
	"chromiumos/test/plan/internal/coveragerules"
	"chromiumos/test/plan/internal/protoio"
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
		return errors.New("-generatetestplanreq must be set iff -out is set")
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
	if err := protoio.ReadBinaryOrJSONPb(r.buildMetadataListPath, buildMetadataList); err != nil {
		return err
	}

	glog.Infof("Read %d SystemImage.Metadata from %s", len(buildMetadataList.Values), r.buildMetadataListPath)

	for _, buildMetadata := range buildMetadataList.Values {
		glog.V(2).Infof("Read BuildMetadata: %s", buildMetadata)
	}

	dutAttributeList := &testpb.DutAttributeList{}
	if err := protoio.ReadBinaryOrJSONPb(r.dutAttributeListPath, dutAttributeList); err != nil {
		return err
	}

	glog.Infof("Read %d DutAttributes from %s", len(dutAttributeList.DutAttributes), r.dutAttributeListPath)

	for _, dutAttribute := range dutAttributeList.DutAttributes {
		glog.V(2).Infof("Read DutAttribute: %s", dutAttribute)
	}

	glog.Infof("Starting read of ConfigBundleList from %s", r.configBundleListPath)

	configBundleList := &payload.ConfigBundleList{}
	if err := protoio.ReadBinaryOrJSONPb(r.configBundleListPath, configBundleList); err != nil {
		return err
	}

	glog.Infof("Read %d ConfigBundles from %s", len(configBundleList.Values), r.configBundleListPath)

	hwTestPlans, vmTestPlans, err := testplan.Generate(
		ctx, r.planPaths, buildMetadataList, dutAttributeList, configBundleList,
	)
	if err != nil {
		return err
	}

	if !r.ctpV1 && len(vmTestPlans) > 0 {
		return fmt.Errorf("VMTestPlans are currently only supported in CTP1 compatibility mode")
	}

	if r.ctpV1 {
		glog.Infof(
			"Outputting GenerateTestPlanRequest to %s instead of HWTestPlan, for backwards compatibility with CTPV1",
			r.out,
		)

		generateTestPlanReq := &testplans.GenerateTestPlanRequest{}
		if err := protoio.ReadBinaryOrJSONPb(r.generateTestPlanReqPath, generateTestPlanReq); err != nil {
			return err
		}

		boardPriorityList := &testplans.BoardPriorityList{}
		if err := protoio.ReadBinaryOrJSONPb(r.boardPriorityListPath, boardPriorityList); err != nil {
			return err
		}

		resp, err := compatibility.ToCTP1(
			rand.New(rand.NewSource(time.Now().Unix())),
			hwTestPlans, vmTestPlans, generateTestPlanReq, dutAttributeList, boardPriorityList,
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

		jsonprotoOut := protoio.FilepathAsJsonpb(r.out)
		if jsonprotoOut == r.out {
			glog.Warningf("Output path set to jsonpb (%q), but output will be written as binaryproto", r.out)
		} else {
			glog.Infof("Writing jsonproto version of output to %s", jsonprotoOut)

			jsonprotoOutFile, err := os.Create(jsonprotoOut)
			if err != nil {
				return err
			}
			defer jsonprotoOutFile.Close()

			jsonprotoRespBytes, err := protojson.Marshal(resp)
			if err != nil {
				return err
			}

			if _, err := jsonprotoOutFile.Write(jsonprotoRespBytes); err != nil {
				return err
			}
		}

		return nil
	}

	glog.Infof("Generated %d CoverageRules, writing to %s", len(hwTestPlans), r.out)

	var messages []proto.Message
	var allRules []*testpb.CoverageRule
	for _, m := range hwTestPlans {
		messages = append(messages, m)
		allRules = append(allRules, m.GetCoverageRules()...)
	}
	if err := protoio.WriteJsonl(messages, r.out); err != nil {
		return err
	}

	if r.textSummaryOut != "" {
		glog.Infof("Writing text summary file to %s", r.textSummaryOut)

		textSummaryOutFile, err := os.Create(r.textSummaryOut)
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

func main() {
	os.Exit(subcommands.Run(application, nil))
}
