// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// The testplan tool generates ChromeOS CoverageRule protos from SourceTestPlan
// protos.
package main

import (
	"bytes"
	"errors"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	buildpb "go.chromium.org/chromiumos/config/go/build/api"
	testpb "go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/chromiumos/config/go/test/plan"
	luciflag "go.chromium.org/luci/common/flag"

	testplan "chromiumos/test/plan/internal"
)

// errToCode converts an error into an exit code.
func errToCode(a subcommands.Application, err error) int {
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %s\n", a.GetName(), err)
		return 1
	}

	return 0
}

var application = &subcommands.DefaultApplication{
	Name:  "testplan",
	Title: "A tool to generate ChromeOS CoverageRule protos from SourceTestPlan protos.",
	Commands: []*subcommands.Command{
		cmdGenerate,

		subcommands.CmdHelp,
	},
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

		return r
	},
}

type generateRun struct {
	subcommands.CommandRunBase
	planPaths            []string
	buildSummaryListPath string
	dutAttributeListPath string
	out                  string
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
func writeRules(rules []*testpb.CoverageRule, outPath string) error {
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

	dutAttributeList := &testpb.DutAttributeList{}
	if err := readJsonpb(r.dutAttributeListPath, dutAttributeList); err != nil {
		return err
	}

	rules, err := testplan.Generate(
		plans, buildSummaryList, dutAttributeList,
	)
	if err != nil {
		return err
	}

	return writeRules(rules, r.out)
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
