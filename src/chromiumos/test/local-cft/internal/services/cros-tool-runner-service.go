// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"chromiumos/test/local-cft/internal/utils"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	buildapi "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/test/api"
)

const (
	_LOGIN_USERNAME       = "oauth2accesstoken"
	_LOGIN_PASSWORD       = "$(gcloud auth print-access-token)"
	_LOGIN_REGISTRY       = "us-docker.pkg.dev"
	IMAGE_DATA_TEMPLATE   = "gs://chromeos-image-archive/%s-release/%s*/metadata/containers.jsonpb"
	CROS_TOOL_RUNNER_PATH = "chromiumos/infra/cros-tool-runner/${platform}"
)

type ctrServiceCommands struct {
	LoginRegistry  ServiceCommand_
	StartContainer ServiceCommand_
}

// Enum of available commands for cros-tool-runner
func CTR_SERVICE_COMMANDS() ctrServiceCommands {
	return ctrServiceCommands{
		LoginRegistry:  "login_registry",
		StartContainer: "start_container",
	}
}

// Service implementation for cros-tool-runner
type CTRService struct {
	Service
	ServiceBase

	client api.CrosToolRunnerContainerServiceClient
}

func (c *CTRService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCTR{
		ctr: c,
	}

	if err := c.executor.Start(starter); err != nil {
		return err
	}

	// Start CacheServer, SSHTunnel, SSHReverseTunnel, CrosDut

	cacheServerService := &CacheServerService{
		ServiceBase: NewServiceBase(
			c.manager,
			c.executor,
			SERVICES().CacheServer,
		),
	}
	sshReverseTunnelService := &SSHTunnelService{
		ServiceBase: NewServiceBase(
			c.manager,
			c.executor,
			SERVICES().SSHReverseTunnel,
		),
	}
	sshTunnelService := &SSHTunnelService{
		ServiceBase: NewServiceBase(
			c.manager,
			c.executor,
			SERVICES().SSHTunnel,
		),
	}
	crosDutService := &CrosDutService{
		ServiceBase: NewServiceBase(
			c.manager,
			c.executor,
			SERVICES().CrosDut,
		),
	}

	if err := c.manager.Start(cacheServerService.Name, cacheServerService); err != nil {
		return err
	}
	if err := c.manager.Start(sshReverseTunnelService.Name, sshReverseTunnelService); err != nil {
		return err
	}
	if err := c.manager.Start(sshTunnelService.Name, sshTunnelService); err != nil {
		return err
	}
	if err := c.manager.Start(crosDutService.Name, crosDutService); err != nil {
		return err
	}

	return nil
}

func (c *CTRService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	var cmd ServiceCommand = nil
	switch commandName {
	case CTR_SERVICE_COMMANDS().LoginRegistry:
		cmd = &LoginRegistryCommand{
			ctr: c,
			request: &api.LoginRegistryRequest{
				Username: _LOGIN_USERNAME,
				Password: _LOGIN_PASSWORD,
				Registry: _LOGIN_REGISTRY,
			},
		}
	case CTR_SERVICE_COMMANDS().StartContainer:
		startContainerRequest := args[0].([]interface{})[0].(*api.StartContainerRequest)

		cmd = &StartContainerCommand{
			ctr:     c,
			request: startContainerRequest,
		}
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
	return c.executor.Execute(cmd)
}

func (c *CTRService) Stop() error {
	stopper := &StopCTR{
		ctr: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCTR struct {
	ServiceSetup
	ctr *CTRService
}

func (starter *SetupCTR) Setup() error {
	path, err := starter.fetchCrosToolRunner()
	if err != nil {
		return nil
	}

	go BuildServiceListener(
		&starter.ctr.ServiceBase,
		false,
		exec.Command(fmt.Sprintf("%s/cros-tool-runner", path), "serve", "-port", fmt.Sprint(starter.ctr.Port)),
	)()

	if err := <-starter.ctr.ReadyChan; err != nil {
		return err
	}

	if err := BuildConnection(&starter.ctr.ServiceBase); err != nil {
		return err
	}
	starter.ctr.client = api.NewCrosToolRunnerContainerServiceClient(starter.ctr.conn)

	if err := starter.ctr.manager.Execute(SERVICES().CrosToolRunner, CTR_SERVICE_COMMANDS().LoginRegistry); err != nil {
		return err
	}

	if err := starter.fetchImageData(); err != nil {
		return fmt.Errorf("could not fetch image data, %s", err)
	}

	return nil
}

func (starter *SetupCTR) fetchCrosToolRunner() (string, error) {
	dir := fmt.Sprintf("%s/bin/", starter.ctr.BaseDir)

	if err := os.RemoveAll(dir); err != nil {
		return "", fmt.Errorf("Failed to remove previous binaries, %s", err)
	}

	if err := os.MkdirAll(dir, 0755); err != nil {
		starter.ctr.LocalLogger.Printf("Failed to create local-cft binaries directory, %s\n", err)
	}
	if _, err := exec.Command("cipd", "init", dir).Output(); err != nil {
		return "", fmt.Errorf("Could not run 'cipd init', %s", err)
	}
	if _, err := exec.Command("cipd", "install", CROS_TOOL_RUNNER_PATH, "prod", "-root", dir).Output(); err != nil {
		return "", fmt.Errorf("Failed to install cros-tool-runner, %s", err)
	}

	return dir, nil
}

func (starter *SetupCTR) fetchImageData() error {
	template := fmt.Sprintf(
		IMAGE_DATA_TEMPLATE,
		starter.ctr.manager.Board,
		starter.ctr.manager.Build,
	)

	gsutil := exec.Command("gsutil", "ls", "-l", template)
	sort := exec.Command("sort", "-k", "2")

	gPipe, err := gsutil.StdoutPipe()
	if err != nil {
		return err
	}

	sort.Stdin = gPipe

	if err := gsutil.Start(); err != nil {
		return err
	}
	imageDataRaw, err := sort.Output()
	if err != nil {
		return err
	}

	regContainerEx := regexp.MustCompile(`gs://.*.jsonpb`)
	containerImages := regContainerEx.FindAllStringSubmatch(string(imageDataRaw), -1)

	if len(containerImages) == 0 {
		return fmt.Errorf("Could not find any container images with given build number %s", starter.ctr.manager.Build)
	}
	archivePath := containerImages[len(containerImages)-1][0]
	starter.ctr.manager.imagePath = strings.Split(archivePath, "metadata")[0] // Add to Manager

	cat := exec.Command("gsutil", "cat", archivePath)

	catOut, err := cat.Output()
	if err != nil {
		return err
	}

	reader := strings.NewReader(string(catOut))

	metadata := &buildapi.ContainerMetadata{}
	unmarshaler := jsonpb.Unmarshaler{}
	unmarshaler.Unmarshal(reader, metadata)
	starter.ctr.manager.images = metadata.Containers[starter.ctr.manager.Board].Images // Add to Manager

	return nil
}

// Stopper

type StopCTR struct {
	ServiceStopper
	ctr *CTRService
}

func (stopper *StopCTR) Stop() error {
	if stopper.ctr.conn != nil {
		stopper.ctr.conn.Close()
	}

	stopper.ctr.CloseChan <- struct{}{}
	<-stopper.ctr.CloseFinishedChan

	WriteLogs(&stopper.ctr.ServiceBase)

	return nil
}

// Commands

type LoginRegistryCommand struct {
	ServiceCommand
	ctr     *CTRService
	request *api.LoginRegistryRequest
}

func (cmd *LoginRegistryCommand) Execute() error {
	_, err := cmd.ctr.client.LoginRegistry(cmd.ctr.manager.ctx, cmd.request)
	return err
}

type StartContainerCommand struct {
	ServiceCommand
	ctr     *CTRService
	request *api.StartContainerRequest
}

func (cmd *StartContainerCommand) Execute() error {
	_, err := cmd.ctr.client.StartContainer(cmd.ctr.manager.ctx, cmd.request)
	return err
}
