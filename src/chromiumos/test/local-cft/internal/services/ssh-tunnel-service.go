// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"chromiumos/test/local-cft/internal/utils"
	"fmt"
	"os/exec"
)

const (
	DUT_CONNECTION_PORT = 22
)

type sshTunnelServiceCommands struct {
}

func SSH_TUNNEL_SERVICE_COMMANDS() sshTunnelServiceCommands {
	return sshTunnelServiceCommands{}
}

// Service implementation for SSH Tunnels
type SSHTunnelService struct {
	Service
	ServiceBase
}

func (c *SSHTunnelService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupSSHTunnel{
		st: c,
	}
	return c.executor.Start(starter)
}

func (c *SSHTunnelService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	switch commandName {
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
}

func (c *SSHTunnelService) Stop() error {
	stopper := &StopSSHTunnel{
		st: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupSSHTunnel struct {
	ServiceSetup
	st *SSHTunnelService
}

func (starter *SetupSSHTunnel) Setup() error {
	if starter.st.Name == SERVICES().SSHTunnel {
		go BuildServiceListener(
			&starter.st.ServiceBase,
			false,
			exec.Command(
				"autossh",
				"-M",
				"0",
				"-o",
				"ServerAliveInterval=5",
				"-o",
				"ServerAliveCountMax=2",
				"-o",
				"UserKnownHostsFile=/dev/null",
				"-o",
				"StrictHostKeyChecking=no",
				"-tt",
				"-L",
				fmt.Sprintf("%d:localhost:%d", starter.st.Port, DUT_CONNECTION_PORT),
				fmt.Sprintf("root@%s", starter.st.manager.DutHost),
				"-N",
			),
		)()
	} else if starter.st.Name == SERVICES().SSHReverseTunnel {
		go BuildServiceListener(
			&starter.st.ServiceBase,
			true,
			exec.Command(
				"autossh",
				"-M",
				"0",
				"-o",
				"ServerAliveInterval=5",
				"-o",
				"ServerAliveCountMax=2",
				"-o",
				"UserKnownHostsFile=/dev/null",
				"-o",
				"StrictHostKeyChecking=no",
				"-tt",
				"-R",
				fmt.Sprintf(
					"%d:localhost:%d",
					starter.st.Port,
					starter.st.manager.ports[SERVICES().CacheServer]),
				fmt.Sprintf("root@%s", starter.st.manager.DutHost),
				"-p",
				fmt.Sprint(DUT_CONNECTION_PORT),
				"-N",
			),
		)()
	}

	return <-starter.st.ReadyChan
}

// Stopper

type StopSSHTunnel struct {
	ServiceStopper
	st *SSHTunnelService
}

func (stopper *StopSSHTunnel) Stop() error {
	stopper.st.CloseChan <- struct{}{}
	<-stopper.st.CloseFinishedChan

	WriteLogs(&stopper.st.ServiceBase)

	return nil
}

// Commands
