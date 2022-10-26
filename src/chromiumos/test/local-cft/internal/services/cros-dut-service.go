// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"chromiumos/test/local-cft/internal/utils"
	"fmt"
	"os/exec"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type crosDutServiceCommands struct {
}

func CROS_DUT_SERVICE_COMMANDS() crosDutServiceCommands {
	return crosDutServiceCommands{}
}

// Service implementation for cros-dut
type CrosDutService struct {
	Service
	ServiceBase

	client api.DutServiceClient
}

func (c *CrosDutService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCrosDut{
		cd: c,
	}
	return c.executor.Start(starter)
}

func (c *CrosDutService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	switch commandName {
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
}

func (c *CrosDutService) Stop() error {
	stopper := &StopCrosDut{
		cd: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCrosDut struct {
	ServiceSetup
	cd *CrosDutService
}

func (starter *SetupCrosDut) Setup() error {
	if err := utils.EnsureContainerAvailable(starter.cd.Name); err != nil {
		err = fmt.Errorf("Failed to ensure container %s was available, %s", starter.cd.Name, err)
		starter.cd.LocalLogger.Println(err)
		return err
	}

	request := &api.StartContainerRequest{
		Name: starter.cd.Name,
		ContainerImage: fmt.Sprintf(
			"us-docker.pkg.dev/cros-registry/test-services/%s:%s",
			starter.cd.Name,
			starter.cd.manager.images[starter.cd.Name].Tags[0],
		),
		AdditionalOptions: &api.StartContainerRequest_Options{
			Expose:  []string{fmt.Sprint(starter.cd.Port)},
			Volume:  []string{fmt.Sprintf("%s/cros-dut:/tmp/cros-dut", starter.cd.BaseDir)},
			Network: "host",
		},
		StartCommand: []string{
			"cros-dut",
			"-dut_address",
			fmt.Sprintf("localhost:%d", starter.cd.manager.ports[SERVICES().SSHTunnel]),
			"-cache_address",
			fmt.Sprintf("%s:%d", "localhost", starter.cd.manager.ports[SERVICES().SSHReverseTunnel]),
			"-port",
			fmt.Sprint(starter.cd.Port),
		},
	}

	starter.cd.manager.Execute(
		SERVICES().CrosToolRunner,
		CTR_SERVICE_COMMANDS().StartContainer,
		request,
	)

	go BuildServiceListener(
		&starter.cd.ServiceBase,
		false,
		exec.Command("docker", "logs", "-f", starter.cd.Name),
	)()

	if err := <-starter.cd.ReadyChan; err != nil {
		starter.cd.LocalLogger.Println(err)
		return err
	}

	if err := BuildConnection(&starter.cd.ServiceBase); err != nil {
		return err
	}
	starter.cd.client = api.NewDutServiceClient(starter.cd.conn)

	return nil
}

// Stopper

type StopCrosDut struct {
	ServiceStopper
	cd *CrosDutService
}

func (stopper *StopCrosDut) Stop() error {
	if stopper.cd.conn != nil {
		stopper.cd.conn.Close()
	}

	stopper.cd.CloseChan <- struct{}{}
	<-stopper.cd.CloseFinishedChan

	WriteLogs(&stopper.cd.ServiceBase)

	return nil
}

// Commands
