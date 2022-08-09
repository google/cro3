// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the server command grouping
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"log"

	// "chromiumos/test/provision/v2/cros-provision/constants"
	// "chromiumos/test/provision/v2/cros-provision/executor"
	"errors"
	"flag"
	"fmt"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

const (
	DefaultPort         = 80
	DefaultLogDirectory = "/tmp/fw-provision/"
)

// ServerCommand executed the provisioning as a Server
type ServerCommand struct {
	req           *api.ProvisionFirmwareRequest
	inputFilename string

	log         *log.Logger
	logFilename string

	port int

	flagSet *flag.FlagSet
}

func NewServerCommand() *ServerCommand {
	sc := &ServerCommand{
		flagSet: flag.NewFlagSet("server", flag.ContinueOnError),
	}

	sc.flagSet.IntVar(&sc.port, "port", DefaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", DefaultPort))
	sc.flagSet.StringVar(&sc.logFilename, "log-path", DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", DefaultLogDirectory))
	sc.flagSet.StringVar(&sc.inputFilename, "input", "",
		"Specify the ProvisionFirmwareRequest input file. "+
			"File must include metadata about DUT, CFT services addresses, but not the request.")
	return sc
}

func (sc *ServerCommand) Is(group string) bool {
	return strings.HasPrefix(group, "server")
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

	sc.log, err = SetUpLog(sc.logFilename)
	if err != nil {
		return fmt.Errorf("unable to set up logs: %s", err)
	}

	req, err := common_utils.ParseProvisionFirmwareRequest(sc.inputFilename)
	if err != nil {
		return fmt.Errorf("unable to parse ProvisionFirmwareRequest proto: %s", err)
	}

	if err = sc.validateProtoInputs(req); err != nil {
		return err
	}
	sc.req = req

	return nil
}

// validateCLIInputs ensures the CLI input values are valid
func (cc *ServerCommand) validateCLIInputs() error {
	if cc.inputFilename == "" {
		return errors.New("input file not specified")
	}
	return nil
}

// validateProtoInputs ensures the proto part of the CLI input is valid
func (cc *ServerCommand) validateProtoInputs(req *api.ProvisionFirmwareRequest) error {
	if len(req.Board) == 0 {
		return errors.New("ProvisionFirmwareRequest: Board field is required ")
	}
	if len(req.Model) == 0 {
		return errors.New("ProvisionFirmwareRequest: Model field is required ")
	}
	if req.UseServo {
		if req.CrosServodAddress == nil {
			return errors.New("ProvisionFirmwareRequest: CrosServodAddress is required when UseServo=true")
		}
	}
	if req.DutServerAddress == nil {
		return errors.New("ProvisionFirmwareRequest: DutServerAddress is required")
	}
	if req.GetSimpleRequest() == nil && req.GetDetailedRequest() == nil {
		return errors.New("ProvisionFirmwareRequest: SimpleRequest or DetailedRequest is required")
	}
	return nil
}

func (sc *ServerCommand) Run() error {
	sc.log.Printf("running server mode:")

	ps, closer, err := NewFWProvisionServer(sc.port, sc.log, sc.req)
	defer closer()
	if err != nil {
		sc.log.Fatalln("failed to create provision: ", err)
		return err
	}

	if err := ps.Start(); err != nil {
		sc.log.Fatalln("failed server execution: ", err)
		return err
	}

	return nil
}
