// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The testplan tool generates ChromeOS CoverageRule protos from SourceTestPlan
// protos.
package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/golang/glog"
	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
	luciflag "go.chromium.org/luci/common/flag"

	testplan "chromiumos/test/plan/internal"
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
	Title: "A tool to generate ChromeOS CoverageRule protos from SourceTestPlan protos.",
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
	UsageLine: "generate -plan PLAN1 [-plan PLAN2] -dutattributes PATH -buildsummary -out OUTPUT",
	ShortDesc: "generate coverage rule protos",
	LongDesc: `Generate coverage rule protos.

Reads SourceTestPlan text protos and generates a CoverageRules as
newline-delimited json protos.
`,
	CommandRun: func() subcommands.CommandRun {
		r := &generateRun{}
		r.Flags.Var(
			luciflag.StringSlice(&r.planPaths),
			"plan",
			"Text proto file with a SourceTestPlan to use. Must be specified "+
				"at least once.",
		)
		r.Flags.StringVar(
			&r.dutAttributeListPath,
			"dutattributes",
			"",
			"Path to a JSON proto file containing a DutAttributeList.",
		)
		r.Flags.StringVar(
			&r.buildSummaryListPath,
			"buildsummary",
			"",
			"Path to a JSON proto file containing a BuildSummaryList.",
		)
		r.Flags.StringVar(
			&r.out,
			"out",
			"",
			"Path to the output CoverageRules.",
		)
		r.Flags.StringVar(
			&r.textSummaryOut,
			"textsummaryout",
			"",
			"Path to write a more easily human-readable summary of the "+
				"CoverageRules to. If not set, no summary is written.",
		)

		r.addExistingFlags()

		return r
	},
}

type generateRun struct {
	subcommands.CommandRunBase
	planPaths            []string
	buildSummaryListPath string
	dutAttributeListPath string
	out                  string
	textSummaryOut       string
}

func (r *generateRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	return errToCode(a, r.run())
}

// readJsonpb reads the jsonpb at path into m.
func readJsonpb(path string, m proto.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	return jsonpb.Unmarshal(bytes.NewReader(b), m)
}

// readTextpb reads the textpb at path into m.
func readTextpb(path string, m proto.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}

	return proto.UnmarshalText(string(b), m)
}

// writeRules writes a newline-delimited json file containing rules to outPath.
func writeRules(rules []*testpb.CoverageRule, outPath, textSummaryOutPath string) error {
	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()

	marshaler := jsonpb.Marshaler{}

	for _, rule := range rules {
		jsonString, err := marshaler.MarshalToString(rule)
		if err != nil {
			return err
		}

		jsonString += "\n"

		if _, err = outFile.Write([]byte(jsonString)); err != nil {
			return err
		}
	}

	if textSummaryOutPath != "" {
		glog.Infof("Writing text summary file to %s", textSummaryOutPath)

		textSummaryOutFile, err := os.Create(textSummaryOutPath)
		if err != nil {
			return err
		}
		defer textSummaryOutFile.Close()

		if err = coveragerules.WriteTextSummary(textSummaryOutFile, rules); err != nil {
			return err
		}
	}

	return nil
}

// validateFlags checks valid flags are passed to generate, e.g. all required
// flags are set.
func (r *generateRun) validateFlags() error {
	if len(r.planPaths) == 0 {
		return errors.New("at least one -plan is required")
	}

	if r.dutAttributeListPath == "" {
		return errors.New("-dutattributes is required")
	}

	if r.buildSummaryListPath == "" {
		return errors.New("-buildsummary is required")
	}

	if r.out == "" {
		return errors.New("-out is required")
	}

	return nil
}

// run is the actual implementation of the generate command.
func (r *generateRun) run() error {
	if err := r.validateFlags(); err != nil {
		return err
	}

	plans := make([]*plan.SourceTestPlan, len(r.planPaths))

	for i, planPath := range r.planPaths {
		plan := &plan.SourceTestPlan{}
		if err := readTextpb(planPath, plan); err != nil {
			return err
		}

		plans[i] = plan
	}

	buildSummaryList := &buildpb.SystemImage_BuildSummaryList{}
	if err := readJsonpb(r.buildSummaryListPath, buildSummaryList); err != nil {
		return err
	}

	glog.Infof("Reading %d BuildSummaries from %s", len(buildSummaryList.Values), r.buildSummaryListPath)

	for _, buildSummary := range buildSummaryList.Values {
		glog.V(2).Infof("Read BuildSummary: %s", buildSummary)
	}

	dutAttributeList := &testpb.DutAttributeList{}
	if err := readJsonpb(r.dutAttributeListPath, dutAttributeList); err != nil {
		return err
	}

	glog.Infof("Reading %d DutAttributes from %s", len(dutAttributeList.DutAttributes), r.dutAttributeListPath)

	for _, dutAttribute := range dutAttributeList.DutAttributes {
		glog.V(2).Infof("Read DutAttribute: %s", dutAttribute)
	}

	rules, err := testplan.Generate(
		plans, buildSummaryList, dutAttributeList,
	)
	if err != nil {
		return err
	}

	glog.Infof("Generated %d CoverageRules, writing to %s", len(rules), r.out)

	return writeRules(rules, r.out, r.textSummaryOut)
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
