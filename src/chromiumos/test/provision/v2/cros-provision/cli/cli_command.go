// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the CLI command grouping
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/constants"
	"chromiumos/test/provision/v2/cros-provision/service"
	state_machine "chromiumos/test/provision/v2/cros-provision/state-machine"
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

var statusToResult = map[api.InstallResponse_Status]api.InstallFailure_Reason{
	api.InstallResponse_STATUS_INVALID_REQUEST:                        api.InstallFailure_REASON_INVALID_REQUEST,
	api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION:          api.InstallFailure_REASON_DUT_UNREACHABLE_PRE_PROVISION,
	api.InstallResponse_STATUS_DOWNLOADING_IMAGE_FAILED:               api.InstallFailure_REASON_DOWNLOADING_IMAGE_FAILED,
	api.InstallResponse_STATUS_PROVISIONING_TIMEDOUT:                  api.InstallFailure_REASON_PROVISIONING_TIMEDOUT,
	api.InstallResponse_STATUS_PROVISIONING_FAILED:                    api.InstallFailure_REASON_PROVISIONING_FAILED,
	api.InstallResponse_STATUS_DUT_UNREACHABLE_POST_PROVISION:         api.InstallFailure_REASON_DUT_UNREACHABLE_POST_PROVISION,
	api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED:                 api.InstallFailure_REASON_UPDATE_FIRMWARE_FAILED,
	api.InstallResponse_STATUS_FIRMWARE_MISMATCH_POST_FIRMWARE_UPDATE: api.InstallFailure_REASON_FIRMWARE_MISMATCH_POST_FIRMWARE_UPDATE,
	api.InstallResponse_STATUS_DUT_UNREACHABLE_POST_FIRMWARE_UPDATE:   api.InstallFailure_REASON_DUT_UNREACHABLE_POST_FIRMWARE_UPDATE,
	api.InstallResponse_STATUS_UPDATE_MINIOS_FAILED:                   api.InstallFailure_REASON_UPDATE_MINIOS_FAILED,
	api.InstallResponse_STATUS_POST_PROVISION_SETUP_FAILED:            api.InstallFailure_REASON_POST_PROVISION_SETUP_FAILED,
	api.InstallResponse_STATUS_CLEAR_TPM_FAILED:                       api.InstallFailure_REASON_CLEAR_TPM_FAILED,
	api.InstallResponse_STATUS_STABLIZE_DUT_FAILED:                    api.InstallFailure_REASON_STABLIZE_DUT_FAILED,
	api.InstallResponse_STATUS_INSTALL_DLC_FAILED:                     api.InstallFailure_REASON_INSTALL_DLC_FAILED,
}

// CLI command executed the provisioning as a CLI
type CLICommand struct {
	logFileName string
	log         *log.Logger
	inputFile   string
	inputProto  *api.CrosProvisionRequest
	outputFile  string
	flagSet     *flag.FlagSet
}

func NewCLICommand() *CLICommand {
	cc := &CLICommand{
		flagSet: flag.NewFlagSet("server", flag.ContinueOnError),
	}

	cc.flagSet.StringVar(&cc.logFileName, "log-path", constants.DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", constants.DefaultLogDirectory))
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

	cc.inputProto, err = common_utils.ParseCrosProvisionRequest(cc.inputFile)
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
	dutAddr := fmt.Sprintf("%s:%d", cc.inputProto.GetDutServer().GetAddress(), cc.inputProto.GetDutServer().GetPort())
	cc.log.Printf("DutAddr found %s", dutAddr)

	dutConn, err := grpc.Dial(dutAddr, grpc.WithInsecure())
	if err != nil {
		cc.log.Printf("DutConn Failed!")
		return fmt.Errorf("failed to connect to dut-service, %s", err)
	}
	cc.log.Printf("Dut Conn Established")

	defer dutConn.Close()
	cs := service.NewCrOSServiceFromCrOSProvisionRequest(api.NewDutServiceClient(dutConn), cc.inputProto)
	cc.log.Printf("New CS Created")

	out := &api.CrosProvisionResponse{
		Id: &lab_api.Dut_Id{
			Value: cc.inputProto.GetDut().GetId().GetValue(),
		},
		Outcome: &api.CrosProvisionResponse_Success{},
	}

	defer saveCLIOutput(cc.outputFile, out, cc.log)
	cc.log.Printf("State Machine Start.")

	if respStatus, _, err := common_utils.ExecuteStateMachine(context.Background(), state_machine.NewCrOSPreInitState(cs), cc.log); err != nil {
		cc.log.Printf("State Machine Failed, setting err to PROVISION_FAILED.")
		translatedStatus := statusToResult[respStatus]
		out.Outcome = &api.CrosProvisionResponse_Failure{
			Failure: &api.InstallFailure{
				Reason: api.InstallFailure_Reason(translatedStatus),
			},
		}
		cc.log.Printf("State Machine Failed %s.", err)
		return fmt.Errorf("failed to provision, %s", err)
	}
	cc.log.Printf("Finished Successfuly!")
	return nil
}

// saveCLIOutput saves response to the output file.
func saveCLIOutput(outputPath string, out *api.CrosProvisionResponse, log *log.Logger) error {
	log.Printf("saveCLIOutput out:%s\n", out)
	if outputPath != "" && out != nil {
		log.Printf("saveCLIOutput outputPath:%s\n", outputPath)
		dir := filepath.Dir(outputPath)
		// Create the directory if it doesn't exist.
		if err := os.MkdirAll(dir, 0777); err != nil {
			log.Printf("MKDIR Error.")
			return fmt.Errorf("save output: fail to create directory for %q", outputPath)
		}
		w, err := os.Create(outputPath)
		if err != nil {
			log.Printf("Save File Error")
			return fmt.Errorf("save output: failed to create file %q", outputPath)
		}
		defer w.Close()

		marshaler := jsonpb.Marshaler{}
		if err := marshaler.Marshal(w, out); err != nil {

			log.Printf("Marshal Error")
			return fmt.Errorf("save output: failed to marshal output")
		}
	} else {
		log.Printf("saveCLIOutput NO OUTPATH")
	}
	return nil
}
