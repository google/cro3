// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the server command grouping
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/common-utils/metadata"
	"chromiumos/test/provision/v2/common-utils/server"
	"chromiumos/test/provision/v2/cros-provision/constants"
	"chromiumos/test/provision/v2/cros-provision/executor"
	"errors"
	"flag"
	"fmt"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// ServerCommand executed the provisioning as a Server
type ServerCommand struct {
	metadata     *metadata.ServerMetadata
	logFileName  string
	metadataFile string
	flagSet      *flag.FlagSet
}

func NewServerCommand() *ServerCommand {
	sc := &ServerCommand{
		flagSet:  flag.NewFlagSet("server", flag.ContinueOnError),
		metadata: &metadata.ServerMetadata{},
	}

	sc.flagSet.IntVar(&sc.metadata.Port, "port", constants.DefaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", constants.DefaultPort))
	sc.flagSet.StringVar(&sc.logFileName, "log-path", constants.DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", constants.DefaultLogDirectory))
	sc.flagSet.StringVar(&sc.metadataFile, "metadata", "", "Specify the request jsonproto input file. Provide service paths and ProvisionState.")
	return sc
}

func (sc *ServerCommand) Is(group string) bool {
	return strings.HasPrefix(group, "s")
}

func (sc *ServerCommand) Name() string {
	return "server"
}

func (sc *ServerCommand) Init(args []string) error {
	err := sc.flagSet.Parse(args)
	if err != nil {
		return err
	}

	if err = sc.validateCLIInputs(); err != nil {
		return err
	}

	sc.metadata.Log, err = SetUpLog(sc.logFileName)
	if err != nil {
		return fmt.Errorf("unable to set up logs: %s", err)
	}

	cpp, err := common_utils.ParseCrosProvisionRequest(sc.metadataFile)
	if err != nil {
		return fmt.Errorf("unable to parse CrosProvisionRequest proto: %s", err)
	}

	if err = sc.validateProtoInputs(cpp); err != nil {
		return err
	}
	sc.metadata.Dut = cpp.GetDut()
	sc.metadata.DutAddress = fmt.Sprintf("%s:%d", cpp.GetDutServer().GetAddress(), cpp.GetDutServer().GetPort())

	return nil
}

// validateCLIInputs ensures the CLI input values are valid
func (cc *ServerCommand) validateCLIInputs() error {
	if cc.metadataFile == "" {
		return errors.New("input file not specified")
	}
	return nil
}

// validateProtoInputs ensures the proto part of the CLI input is valid
func (cc *ServerCommand) validateProtoInputs(cpp *api.CrosProvisionRequest) error {
	if cpp.GetDut() == nil || cpp.GetDut().GetId().GetValue() == "" {
		return errors.New("dut id is not specified in input file")
	}
	if cpp.GetDutServer() == nil || cpp.DutServer.GetAddress() == "" || cpp.DutServer.GetPort() <= 0 {
		return errors.New("dut server address is no specified or incorrect in input file")
	}
	return nil
}

func (sc *ServerCommand) Run() error {
	sc.metadata.Log.Printf("running server mode:")

	ps, closer, err := server.NewProvisionServer(sc.metadata, &executor.CrOSProvisionExecutor{})
	defer closer()
	if err != nil {
		sc.metadata.Log.Fatalln("failed to create provision: ", err)
		return err
	}

	if err := ps.Start(); err != nil {
		sc.metadata.Log.Fatalln("failed server execution: ", err)
		return err
	}

	return nil
}
