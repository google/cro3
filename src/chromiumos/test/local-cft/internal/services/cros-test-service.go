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
	lab "go.chromium.org/chromiumos/config/go/test/lab/api"
)

type crosTestServiceCommands struct {
	RunTests ServiceCommand_
}

// Enum of available commands for cros-test
func CROS_TEST_SERVICE_COMMANDS() crosTestServiceCommands {
	return crosTestServiceCommands{
		RunTests: "run-tests",
	}
}

// Service implementation for cros-test
type CrosTestService struct {
	Service
	ServiceBase

	client api.ExecutionServiceClient
}

func (c *CrosTestService) Start() error {
	c.Port = 8001 //utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCrosTest{
		ct: c,
	}
	return c.executor.Start(starter)
}

func (c *CrosTestService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	var cmd ServiceCommand = nil
	switch commandName {
	case CROS_TEST_SERVICE_COMMANDS().RunTests:
		cmd = &RunTestsCommand{
			ct: c,
		}
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
	return c.executor.Execute(cmd)
}

func (c *CrosTestService) Stop() error {
	stopper := &StopCrosTest{
		ct: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCrosTest struct {
	ServiceSetup
	ct *CrosTestService
}

func (starter *SetupCrosTest) Setup() error {
	if err := utils.EnsureContainerAvailable(starter.ct.Name); err != nil {
		err = fmt.Errorf("Failed to ensure container %s was available, %s", starter.ct.Name, err)
		starter.ct.LocalLogger.Println(err)
		return err
	}

	request := &api.StartContainerRequest{
		Name: starter.ct.Name,
		ContainerImage: fmt.Sprintf(
			"us-docker.pkg.dev/cros-registry/test-services/%s:%s",
			starter.ct.Name,
			starter.ct.manager.images[starter.ct.Name].Tags[0],
		),
		AdditionalOptions: &api.StartContainerRequest_Options{
			Expose: []string{fmt.Sprint(starter.ct.Port)},
			Volume: []string{
				fmt.Sprintf("%s/unit-tests/cros-test/cros-test:/tmp/test/cros-test", starter.ct.BaseDir),
				fmt.Sprintf("%s/unit-tests/cros-test/results:/tmp/test/results", starter.ct.BaseDir),
			},
			Network: "host",
		},
		StartCommand: []string{
			"bash",
			"-c",
			fmt.Sprintf("sudo --non-interactive chown -R chromeos-test:chromeos-test /tmp/test && cros-test server -port %d", starter.ct.Port),
		},
	}

	starter.ct.manager.Execute(
		SERVICES().CrosToolRunner,
		CTR_SERVICE_COMMANDS().StartContainer,
		request,
	)

	go BuildServiceListener(
		&starter.ct.ServiceBase,
		false,
		exec.Command("docker", "logs", "-f", starter.ct.Name),
	)()

	if err := <-starter.ct.ReadyChan; err != nil {
		starter.ct.LocalLogger.Println(err)
		return err
	}

	if err := BuildConnection(&starter.ct.ServiceBase); err != nil {
		return err
	}
	starter.ct.client = api.NewExecutionServiceClient(starter.ct.conn)

	return nil
}

// Stopper

type StopCrosTest struct {
	ServiceStopper
	ct *CrosTestService
}

func (stopper *StopCrosTest) Stop() error {
	if stopper.ct.conn != nil {
		stopper.ct.conn.Close()
	}

	stopper.ct.CloseChan <- struct{}{}
	<-stopper.ct.CloseFinishedChan

	WriteLogs(&stopper.ct.ServiceBase)

	return nil
}

// Commands

type RunTestsCommand struct {
	ServiceCommand
	ct *CrosTestService
}

func (cmd *RunTestsCommand) Execute() error {
	runTestsRequest := &api.CrosTestRequest{
		TestSuites: cmd.ct.manager.testSuites,
		Primary: &api.CrosTestRequest_Device{
			Dut: &lab.Dut{
				Id: &lab.Dut_Id{
					Value: "localhost",
				},
				DutType: &lab.Dut_Chromeos{
					Chromeos: &lab.Dut_ChromeOS{
						Ssh: &lab.IpEndpoint{
							Address: "localhost",
							Port:    int32(cmd.ct.manager.ports[SERVICES().SSHTunnel]),
						},
						DutModel: &lab.DutModel{
							BuildTarget: "nautilus",
							ModelName:   "nautilus",
						},
						Servo: &lab.Servo{
							Present: false,
						},
					},
				},
			},
			DutServer: &lab.IpEndpoint{
				Address: "localhost",
				Port:    int32(cmd.ct.manager.ports[SERVICES().CrosDut]),
			},
			ProvisionServer: &lab.IpEndpoint{
				Address: "localhost",
				Port:    int32(cmd.ct.manager.ports[SERVICES().CrosProvision]),
			},
		},
	}

	runTestResponse, err := cmd.ct.client.RunTests(cmd.ct.manager.ctx, runTestsRequest)
	if err != nil {
		return fmt.Errorf("Failed to run tests, %s", err)
	}

	if !runTestResponse.GetResponse().MessageIs((*api.CrosTestResponse)(nil)) {
		return fmt.Errorf("Response from RunTest was not of type CrosTestResponse")
	}

	testResponse := &api.CrosTestResponse{}
	if err := runTestResponse.GetResponse().UnmarshalTo(testResponse); err != nil {
		return err
	}

	cmd.ct.manager.testResponse = testResponse

	return nil
}
