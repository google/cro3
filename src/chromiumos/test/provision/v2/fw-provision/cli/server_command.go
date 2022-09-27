// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the server command grouping
package cli

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"flag"
	"fmt"
	"log"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

const (
	DefaultPort         = 8080
	DefaultLogDirectory = "/tmp/fw-provision/"
)

// ServerCommand executed the provisioning as a Server
type ServerCommand struct {
	log         *log.Logger
	logFilename string

	// inputFilename expects ProvisionFirmwareRequest and will parse
	// crosDutAddr and crosServodAddr from it, but not the request.
	// Users that want it to parse both the address and the request
	// are looking for `cli` mode, not `server`.
	inputFilename  string
	crosDutAddr    *lab_api.IpEndpoint
	crosServodAddr *lab_api.IpEndpoint

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
	if len(sc.inputFilename) > 0 {
		req, err := common_utils.ParseProvisionFirmwareRequest(sc.inputFilename)
		if err != nil {
			return fmt.Errorf("unable to parse input ProvisionFirmwareRequest: %s", err)
		}
		sc.crosDutAddr = req.DutServerAddress
		sc.crosServodAddr = req.CrosServodAddress
	}

	return nil
}

// validateCLIInputs ensures the CLI input values are valid
func (cc *ServerCommand) validateCLIInputs() error {
	return nil
}

func (sc *ServerCommand) Run() error {
	sc.log.Printf("running server mode:")

	var dutAdapter common_utils.ServiceAdapterInterface
	var err error
	if sc.crosDutAddr != nil {
		dutAdapter, err = connectToDutServer(sc.crosDutAddr)
		if err != nil {
			return err
		}
	}

	var servodServiceClient api.ServodServiceClient
	if sc.crosServodAddr != nil {
		servodServiceClient, err = connectToCrosServod(sc.crosServodAddr)
		if err != nil {
			return err
		}
	}

	ps, closer, err := NewFWProvisionServer(sc.port, sc.log, dutAdapter, servodServiceClient)
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
