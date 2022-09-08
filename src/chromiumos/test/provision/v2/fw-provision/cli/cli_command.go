// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the CLI command grouping
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	firmwareservice "chromiumos/test/provision/v2/fw-provision/service"
	state_machine "chromiumos/test/provision/v2/fw-provision/state-machine"
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang/protobuf/jsonpb"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

const (
	// version is the version info of this command. It is filled in during emerge.
	version             = "<unknown>"
	defaultLogDirectory = "/tmp/fw-provision/"
	defaultPort         = 80
)

// CLI command executed the provisioning as a CLI
type CLICommand struct {
	logFileName string
	log         *log.Logger
	inputFile   string
	inputProto  *api.ProvisionFirmwareRequest
	outputFile  string
	flagSet     *flag.FlagSet
}

func NewCLICommand() *CLICommand {
	cc := &CLICommand{
		flagSet: flag.NewFlagSet("server", flag.ContinueOnError),
	}

	cc.flagSet.StringVar(&cc.logFileName, "log-path", defaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", defaultLogDirectory))
	cc.flagSet.StringVar(&cc.inputFile, "input", "", "Specify the request jsonproto input file. Provide service paths and ProvisionState.")
	cc.flagSet.StringVar(&cc.outputFile, "output", "", "Specify the response jsonproto output file. Empty placeholder file to provide result from provisioning the DUT.")
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

	cc.log, err = SetUpLog(cc.logFileName)
	if err != nil {
		return err
	}

	if err = cc.validate(); err != nil {
		return err
	}

	cc.inputProto, err = common_utils.ParseProvisionFirmwareRequest(cc.inputFile)
	if err != nil {
		return fmt.Errorf("unable to parse CrosProvisionRequest proto: %s", err)
	}

	return nil
}

// Logger returns the log
func (cc *CLICommand) Logger() *log.Logger {
	return cc.log
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

func (cc *CLICommand) Run() error {
	cc.log.Printf("Running CLI Mode (V2):")
	dutAddr := fmt.Sprintf("%s:%d", cc.inputProto.GetDutServerAddress().GetAddress(), cc.inputProto.GetDutServerAddress().GetPort())
	dutConn, err := grpc.Dial(dutAddr, grpc.WithInsecure())
	if err != nil {
		return fmt.Errorf("failed to connect to dut-service, %s", err)
	}
	defer dutConn.Close()

	dutAdapter := common_utils.NewServiceAdapter(api.NewDutServiceClient(dutConn), false /*noReboot*/)

	out := &api.ProvisionFirmwareResponse{}
	defer saveCLIOutput(cc.outputFile, out)

	ctx := context.Background()
	fwService, err := firmwareservice.NewFirmwareService(ctx, dutAdapter, nil, cc.inputProto)
	if err != nil {
		if fwErr, ok := err.(*firmwareservice.FirmwareProvisionError); ok {
			out.Status = fwErr.Status
		} else {
			log.Printf("expected FirmwareProvision to return error of type FirmwareProvisionError. got: %T", err)
			out.Status = api.ProvisionFirmwareResponse_STATUS_UPDATE_FIRMWARE_FAILED
		}
		return err
	}

	// Execute state machine
	cs := state_machine.NewFirmwarePrepareState(fwService)
	for cs != nil {
		if err = cs.Execute(ctx); err != nil {
			break
		}
		cs = cs.Next()
	}

	if err == nil {
		log.Println("Finished Successfuly!")
		return nil
	}
	if fwErr, ok := err.(*firmwareservice.FirmwareProvisionError); ok {
		out.Status = fwErr.Status
	} else {
		log.Printf("expected FirmwareProvision to return error of type FirmwareProvisionError. got: %T", err)
		out.Status = api.ProvisionFirmwareResponse_STATUS_UPDATE_FIRMWARE_FAILED
	}
	return fmt.Errorf("failed to provision: %s", err)
}

// saveCLIOutput saves response to the output file.
func saveCLIOutput(outputPath string, out *api.ProvisionFirmwareResponse) error {
	if outputPath != "" && out != nil {
		dir := filepath.Dir(outputPath)
		// Create the directory if it doesn't exist.
		if err := os.MkdirAll(dir, 0777); err != nil {
			return fmt.Errorf("save output: fail to create directory for %q", outputPath)
		}
		w, err := os.Create(outputPath)
		if err != nil {
			return fmt.Errorf("save output: failed to create file %q", outputPath)
		}
		defer w.Close()

		marshaler := jsonpb.Marshaler{}
		if err := marshaler.Marshal(w, out); err != nil {
			return fmt.Errorf("save output: failed to marshal output")
		}
	}
	return nil
}
