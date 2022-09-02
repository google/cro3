// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the CLI command grouping
package cli

import (
	common_utils "chromiumos/test/publish/cmd/common-utils"
	"chromiumos/test/publish/cmd/rdb-publish/constants"
	"chromiumos/test/publish/cmd/rdb-publish/service"
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/encoding/protojson"
)

// CLI command executed the provisioning as a CLI
type CLICommand struct {
	logFileName string
	inputFile   string
	inputProto  *api.PublishRequest
	outputFile  string
	flagSet     *flag.FlagSet
}

func NewCLICommand() *CLICommand {
	cc := &CLICommand{
		flagSet: flag.NewFlagSet("server", flag.ContinueOnError),
	}

	cc.flagSet.StringVar(&cc.logFileName, "log-path", constants.DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", constants.DefaultLogDirectory))
	cc.flagSet.StringVar(&cc.inputFile, "input", "", "Specify the request jsonproto input file. Must provide local artifact directory path.")
	cc.flagSet.StringVar(&cc.outputFile, "output", "", "Specify the response jsonproto output file. Empty placeholder file to provide result from publishing the artifacts.")
	return cc
}

func (cc *CLICommand) Is(group string) bool {
	return strings.HasPrefix(group, "c")
}

func (cc *CLICommand) Name() string {
	return "cli"
}

func (cc *CLICommand) Init(args []string) error {
	err := cc.flagSet.Parse(args)
	if err != nil {
		return err
	}

	if SetUpLog(cc.logFileName); err != nil {
		return err
	}

	if err = cc.validate(); err != nil {
		return err
	}

	cc.inputProto, err = common_utils.ParsePublishRequest(cc.inputFile)
	if err != nil {
		return fmt.Errorf("unable to parse PublishRequest proto: %s", err)
	}

	return nil
}

// validate checks if inputs are ok
func (cc *CLICommand) validate() error {
	if cc.inputFile == "" {
		return errors.New("input file not specified")
	}

	if cc.outputFile == "" {
		return errors.New("output file not specified")
	}
	return nil
}

// Run runs the commands to publish test results
func (cc *CLICommand) Run() error {
	log.Printf("Running CLI Mode:")

	out := &api.PublishResponse{
		Status: api.PublishResponse_STATUS_SUCCESS,
	}
	defer saveCLIOutput(cc.outputFile, out)

	ps, err := service.NewRdbPublishService(cc.inputProto)
	if err != nil {
		log.Printf("failed to create new rdb publish service: %s", err)
		out.Status = api.PublishResponse_STATUS_INVALID_REQUEST
		out.Message = fmt.Sprintf("failed to create new rdb publish service: %s", err.Error())
		return fmt.Errorf("failed to create new rdb publish service: %s", err)
	}

	if err := ps.UploadToRdb(context.Background()); err != nil {
		log.Printf("upload to rdb failed: %s", err)
		out.Status = api.PublishResponse_STATUS_FAILURE
		out.Message = fmt.Sprintf("failed upload to rdb: %s", err.Error())
		return fmt.Errorf("failed upload to rdb: %s", err)
	}
	log.Println("Finished Successfuly!")
	return nil
}

// saveCLIOutput saves response to the output file.
func saveCLIOutput(outputPath string, out *api.PublishResponse) error {
	if outputPath != "" && out != nil {
		dir := filepath.Dir(outputPath)
		// Create the directory if it doesn't exist.
		if err := os.MkdirAll(dir, 0777); err != nil {
			return fmt.Errorf("save output: failed to create directory for %q", dir)
		}
		w, err := os.Create(outputPath)
		if err != nil {
			return fmt.Errorf("save output: failed to create file %q", outputPath)
		}
		defer w.Close()

		marshaler := protojson.MarshalOptions{
			Multiline: true,
		}

		data, err := marshaler.Marshal(out)
		if err != nil {
			return fmt.Errorf("failed to marshal output: %s", err)
		}

		if err = os.WriteFile(w.Name(), data, 0666); err != nil {
			return fmt.Errorf("failed to write output: %s", err)
		}
	}
	return nil
}
