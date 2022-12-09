// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"chromiumos/test/local-cft/internal/utils"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"

	"github.com/golang/protobuf/jsonpb"
	_go "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab "go.chromium.org/chromiumos/config/go/test/lab/api"
	"google.golang.org/protobuf/types/known/anypb"
)

const (
	PROVISION_METADATA_PATH = "/tmp/provisionservice/in.json"
)

type crosProvisionServiceCommands struct {
	Install ServiceCommand_
}

// Enum of available commands for cros-provision
func CROS_PROVISION_SERVICE_COMMANDS() crosProvisionServiceCommands {
	return crosProvisionServiceCommands{
		Install: "install",
	}
}

// Service implementation for cros-provision
type CrosProvisionService struct {
	Service
	ServiceBase

	client api.GenericProvisionServiceClient
}

func (c *CrosProvisionService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCrosProvision{
		cp: c,
	}
	return c.executor.Start(starter)
}

func (c *CrosProvisionService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	var cmd ServiceCommand = nil
	switch commandName {
	case CROS_PROVISION_SERVICE_COMMANDS().Install:
		cmd = &InstallCommand{
			cp: c,
		}
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
	return c.executor.Execute(cmd)
}

func (c *CrosProvisionService) Stop() error {
	stopper := &StopCrosProvision{
		cp: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCrosProvision struct {
	ServiceSetup
	cp *CrosProvisionService
}

func (starter *SetupCrosProvision) Setup() error {
	if err := utils.EnsureContainerAvailable(starter.cp.Name); err != nil {
		err = fmt.Errorf("Failed to ensure container %s was available, %s", starter.cp.Name, err)
		starter.cp.LocalLogger.Println(err)
		return err
	}

	if err := starter.createProvisionMetadata(); err != nil {
		starter.cp.LocalLogger.Println(err)
		return err
	}

	containerImage := fmt.Sprintf(
		"us-docker.pkg.dev/cros-registry/test-services/%s:%s",
		starter.cp.Name,
		starter.cp.manager.images[starter.cp.Name].Tags[0],
	)

	if _, ok := starter.cp.manager.LocalServices[starter.cp.Name]; ok {
		err := utils.UpdateContainerService(starter.cp.LocalLogger, starter.cp.manager.Chroot, containerImage, starter.cp.Name)
		if err != nil {
			starter.cp.LocalLogger.Println(err)
			return err
		}
		containerImage = containerImage + "_localchange"
	}

	request := &api.StartContainerRequest{
		Name:           starter.cp.Name,
		ContainerImage: containerImage,
		AdditionalOptions: &api.StartContainerRequest_Options{
			Expose:  []string{fmt.Sprint(starter.cp.Port)},
			Volume:  []string{fmt.Sprintf("%s/cros-provision:/tmp/provisionservice", starter.cp.BaseDir)},
			Network: "host",
		},
		StartCommand: []string{
			"cros-provision",
			"server",
			"-metadata",
			PROVISION_METADATA_PATH,
			"-port",
			fmt.Sprint(starter.cp.Port),
		},
	}

	starter.cp.manager.Execute(
		SERVICES().CrosToolRunner,
		CTR_SERVICE_COMMANDS().StartContainer,
		request,
	)

	go BuildServiceListener(
		&starter.cp.ServiceBase,
		false,
		exec.Command("docker", "logs", "-f", starter.cp.Name),
	)()

	if err := <-starter.cp.ReadyChan; err != nil {
		starter.cp.LocalLogger.Println(err)
		return err
	}

	if err := BuildConnection(&starter.cp.ServiceBase); err != nil {
		return err
	}
	starter.cp.client = api.NewGenericProvisionServiceClient(starter.cp.conn)

	return nil
}

func (starter *SetupCrosProvision) createProvisionMetadata() error {
	metadata := &api.CrosProvisionRequest{
		Dut: &lab.Dut{
			Id: &lab.Dut_Id{
				Value: "localhost",
			},
			DutType: &lab.Dut_Chromeos{
				Chromeos: &lab.Dut_ChromeOS{
					Ssh: &lab.IpEndpoint{
						Address: "localhost",
						Port:    int32(starter.cp.Port),
					},
					DutModel: &lab.DutModel{
						BuildTarget: starter.cp.manager.Board,
						ModelName:   starter.cp.manager.Model,
					},
					Servo: &lab.Servo{
						Present: false,
					},
				},
			},
		},
		ProvisionState: &api.ProvisionState{
			SystemImage: &api.ProvisionState_SystemImage{
				SystemImagePath: &_go.StoragePath{
					HostType: _go.StoragePath_GS,
					Path:     starter.cp.manager.imagePath,
				},
			},
		},
		DutServer: &lab.IpEndpoint{
			Address: "localhost",
			Port:    int32(starter.cp.manager.ports[SERVICES().CrosDut]),
		},
	}

	marshaler := jsonpb.Marshaler{}

	metaDataJson, err := marshaler.MarshalToString(metadata)
	if err != nil {
		return fmt.Errorf("Failed to marshal provision request, %s", err)
	}

	if err := os.MkdirAll(fmt.Sprintf("%s/cros-provision/", starter.cp.BaseDir), 0755); err != nil {
		return fmt.Errorf("Error creating cros-provision folder, %s", err)
	}

	err = ioutil.WriteFile(fmt.Sprintf("%s/cros-provision/in.json", starter.cp.BaseDir), []byte(metaDataJson), 0644)
	if err != nil {
		return fmt.Errorf("Error writing provision request to file, %s", err)
	}

	return nil
}

// Stopper

type StopCrosProvision struct {
	ServiceStopper
	cp *CrosProvisionService
}

func (stopper *StopCrosProvision) Stop() error {
	if stopper.cp.conn != nil {
		stopper.cp.conn.Close()
	}

	if stopper.cp.Started {
		stopper.cp.CloseChan <- struct{}{}
		<-stopper.cp.CloseFinishedChan
	}

	WriteLogs(&stopper.cp.ServiceBase)

	return nil
}

// Commands

type InstallCommand struct {
	ServiceCommand
	cp *CrosProvisionService
}

func (cmd *InstallCommand) Execute() error {
	provisionInstallMetadata, err := anypb.New(&api.CrOSProvisionMetadata{})
	if err != nil {
		return fmt.Errorf("Provision input metadata failed marshal, %s", err)
	}
	installRequest := &api.InstallRequest{
		ImagePath: &_go.StoragePath{
			HostType: _go.StoragePath_GS,
			Path:     cmd.cp.manager.imagePath,
		},
		PreventReboot: false,
		Metadata:      provisionInstallMetadata,
	}

	_, err = cmd.cp.client.Install(cmd.cp.manager.ctx, installRequest)
	if err != nil {
		return fmt.Errorf("failed to install, %s", err)
	}

	return nil
}
