// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Represents the server command grouping
package cli

import (
	"chromiumos/test/publish/cmd/common-utils/metadata"
	"chromiumos/test/publish/cmd/cpcon-publish/constants"
	"chromiumos/test/publish/cmd/cpcon-publish/server"
	"flag"
	"fmt"
	"log"
	"strings"
)

// ServerCommand executed the provisioning as a Server
type ServerCommand struct {
	metadata    *metadata.ServerMetadata
	logFileName string
	flagSet     *flag.FlagSet
}

func NewServerCommand() *ServerCommand {
	sc := &ServerCommand{
		flagSet:  flag.NewFlagSet("server", flag.ContinueOnError),
		metadata: &metadata.ServerMetadata{},
	}

	sc.flagSet.IntVar(&sc.metadata.Port, "port", constants.DefaultPort, fmt.Sprintf("Specify the port for the server. Default value %d.", constants.DefaultPort))
	sc.flagSet.StringVar(&sc.logFileName, "log-path", constants.DefaultLogDirectory, fmt.Sprintf("Path to record execution logs. Default value is %s", constants.DefaultLogDirectory))
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

	if err = SetUpLog(sc.logFileName); err != nil {
		return fmt.Errorf("unable to set up logs: %s", err)
	}

	return nil
}

func (sc *ServerCommand) Run() error {
	log.Printf("running server mode:")

	ps, closer, err := server.NewCpconPublishServer(sc.metadata)
	defer closer()
	if err != nil {
		log.Fatalln("failed to create provision: ", err)
		return err
	}

	if err := ps.Start(); err != nil {
		log.Fatalln("failed server execution: ", err)
		return err
	}

	return nil
}
