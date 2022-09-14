// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the server command grouping
package cli

import (
	"log"

	// "chromiumos/test/provision/v2/cros-provision/constants"
	// "chromiumos/test/provision/v2/cros-provision/executor"

	"flag"
	"fmt"
	"strings"
)

const (
	DefaultPort         = 8080
	DefaultLogDirectory = "/tmp/fw-provision/"
)

// ServerCommand executed the provisioning as a Server
type ServerCommand struct {
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

	return nil
}

// validateCLIInputs ensures the CLI input values are valid
func (cc *ServerCommand) validateCLIInputs() error {
	return nil
}

func (sc *ServerCommand) Run() error {
	sc.log.Printf("running server mode:")

	ps, closer, err := NewFWProvisionServer(sc.port, sc.log)
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
