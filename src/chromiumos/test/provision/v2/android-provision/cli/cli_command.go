// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cli

import (
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
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
	state_machine "chromiumos/test/provision/v2/android-provision/state-machine"
	"chromiumos/test/provision/v2/android-provision/test"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

var statusToResult = map[api.InstallResponse_Status]api.InstallFailure_Reason{
	api.InstallResponse_STATUS_INVALID_REQUEST:               api.InstallFailure_REASON_INVALID_REQUEST,
	api.InstallResponse_STATUS_DUT_UNREACHABLE_PRE_PROVISION: api.InstallFailure_REASON_DUT_UNREACHABLE_PRE_PROVISION,
	api.InstallResponse_STATUS_DOWNLOADING_IMAGE_FAILED:      api.InstallFailure_REASON_DOWNLOADING_IMAGE_FAILED,
	api.InstallResponse_STATUS_PROVISIONING_FAILED:           api.InstallFailure_REASON_PROVISIONING_FAILED,
	api.InstallResponse_STATUS_POST_PROVISION_SETUP_FAILED:   api.InstallFailure_REASON_POST_PROVISION_SETUP_FAILED,
	api.InstallResponse_STATUS_PRE_PROVISION_SETUP_FAILED:    api.InstallFailure_REASON_PRE_PROVISION_SETUP_FAILED,
	api.InstallResponse_STATUS_CIPD_PACKAGE_LOOKUP_FAILED:    api.InstallFailure_REASON_CIPD_PACKAGE_LOOKUP_FAILED,
	api.InstallResponse_STATUS_CIPD_PACKAGE_FETCH_FAILED:     api.InstallFailure_REASON_CIPD_PACKAGE_FETCH_FAILED,
	api.InstallResponse_STATUS_GS_UPLOAD_FAILED:              api.InstallFailure_REASON_GS_UPLOAD_FAILED,
	api.InstallResponse_STATUS_GS_DOWNLOAD_FAILED:            api.InstallFailure_REASON_GS_DOWNLOAD_FAILED,
}

// CLICommand executed the provisioning as a CLI
type CLICommand struct {
	logFileName string
	log         *log.Logger
	inputFile   string
	inputProto  *api.AndroidProvisionRequest
	outputFile  string
	flagSet     *flag.FlagSet
}

func NewCLICommand() *CLICommand {
	cc := &CLICommand{
		flagSet: flag.NewFlagSet("server", flag.ContinueOnError),
	}

	cc.flagSet.StringVar(&cc.logFileName, "log-path", common.DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", common.DefaultLogDirectory))
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

	cc.log, err = common.SetUpLog(cc.logFileName)
	if err != nil {
		return err
	}

	if err = cc.validate(); err != nil {
		return err
	}

	cc.inputProto, err = common_utils.ParseAndroidProvisionRequest(cc.inputFile)
	if err != nil {
		return fmt.Errorf("unable to parse AndroidProvisionRequest proto: %s", err)
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
	cc.log.Printf("DutAddr: %s", dutAddr)
	dutConn, err := grpc.Dial(dutAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return fmt.Errorf("failed to connect to dut-service: %s", err)
	}
	cc.log.Printf("Dut Conn Established")
	defer dutConn.Close()
	ip := cc.inputProto.GetDutServer().GetAddress()
	var svc *service.AndroidService
	// Use local adapter for testing. See testing folder.
	if ip == "127.0.0.1" {
		svcAdapter, err := test.NewLocalDutServiceAdapter(cc.inputProto.GetDutServer())
		if err != nil {
			return fmt.Errorf("failed to create AndroidService: %s", err)
		}
		svc, err = service.NewAndroidServiceFromExistingConnection(svcAdapter, cc.inputProto.GetDut().GetAndroid().GetSerialNumber(), cc.inputProto.GetProvisionState().GetAndroidOsImage(), cc.inputProto.GetProvisionState().GetCipdPackages())
		if err != nil {
			return fmt.Errorf("failed to create Android service: %s", err)
		}
	} else {
		svc, err = service.NewAndroidServiceFromAndroidProvisionRequest(api.NewDutServiceClient(dutConn), cc.inputProto)
	}
	cc.log.Printf("New AndroidService Created")
	out := &api.AndroidProvisionCLIResponse{
		Id: &lab_api.Dut_Id{
			Value: cc.inputProto.GetDut().GetId().GetValue(),
		},
		Outcome: &api.AndroidProvisionCLIResponse_Success{},
	}
	defer cc.saveResponse(out)
	cc.log.Printf("Starting State Machine.")
	respStatus, _, err := common_utils.ExecuteStateMachine(context.Background(), state_machine.NewPrepareState(svc), cc.log)
	for _, pkg := range svc.ProvisionPackages {
		if androidPkg := pkg.AndroidPackage; androidPkg != nil && androidPkg.UpdatedVersionCode != "" {
			installedPkg := &api.InstalledAndroidPackage{
				Name:        androidPkg.PackageName,
				VersionCode: androidPkg.UpdatedVersionCode,
			}
			out.AndroidPackages = append(out.AndroidPackages, installedPkg)
		}
	}
	if err != nil {
		cc.log.Printf("State Machine Failed: %v", err)
		translatedStatus := statusToResult[respStatus]
		out.Outcome = &api.AndroidProvisionCLIResponse_Failure{
			Failure: &api.InstallFailure{
				Reason: api.InstallFailure_Reason(translatedStatus),
			},
		}
		return fmt.Errorf("failed to provision, %s", err)
	}
	return nil
}

// saveResponse saves response to the output file.
func (cc *CLICommand) saveResponse(out *api.AndroidProvisionCLIResponse) error {
	cc.log.Printf("saveCLIOutput out:%s\n", out)
	if cc.outputFile != "" && out != nil {
		dir := filepath.Dir(cc.outputFile)
		// Create the directory if it doesn't exist.
		if err := os.MkdirAll(dir, 0777); err != nil {
			return fmt.Errorf("save output: fail to create directory for %q", cc.outputFile)
		}
		w, err := os.Create(cc.outputFile)
		if err != nil {
			return fmt.Errorf("save output: failed to create file %q", cc.outputFile)
		}
		defer w.Close()

		m := jsonpb.Marshaler{}
		if err := m.Marshal(w, out); err != nil {
			return fmt.Errorf("save output: failed to marshal output")
		}
	}
	return nil
}
