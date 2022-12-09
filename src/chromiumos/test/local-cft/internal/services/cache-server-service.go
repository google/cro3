// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"chromiumos/test/local-cft/internal/utils"
	"fmt"
	"os/exec"
	"os/user"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type cacheServerServiceCommands struct {
}

func CACHE_SERVER_SERVICE_COMMANDS() cacheServerServiceCommands {
	return cacheServerServiceCommands{}
}

// Service implementation for the cache server
type CacheServerService struct {
	Service
	ServiceBase
}

func (c *CacheServerService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCacheServer{
		cs: c,
	}
	return c.executor.Start(starter)
}

func (c *CacheServerService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	switch commandName {
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
}

func (c *CacheServerService) Stop() error {
	stopper := &StopCacheServer{
		cs: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCacheServer struct {
	ServiceSetup
	cs *CacheServerService
}

func (starter *SetupCacheServer) Setup() error {
	if err := utils.EnsureContainerAvailable(starter.cs.Name); err != nil {
		err = fmt.Errorf("Failed to ensure container %s was available, %s", starter.cs.Name, err)
		starter.cs.LocalLogger.Println(err)
		return err
	}

	userPath, err := user.Current()
	if err != nil {
		return err
	}
	request := &api.StartContainerRequest{
		Name: starter.cs.Name,
		ContainerImage: fmt.Sprintf(
			"us-docker.pkg.dev/cros-registry/test-services/%s:%s",
			SERVICES().CrosTest,
			SERVICES().CacheServer,
		),
		AdditionalOptions: &api.StartContainerRequest_Options{
			Expose: []string{fmt.Sprint(starter.cs.Port)},
			Volume: []string{
				fmt.Sprintf("%s/.config/:/root/.config", userPath.HomeDir),
				fmt.Sprintf("%s/cacheserver:/tmp/cacheserver", starter.cs.BaseDir),
			},
			Network: "host",
		},
		StartCommand: []string{
			"cacheserver",
			"-location",
			"/tmp/cacheserver",
			"-port",
			fmt.Sprint(starter.cs.Port),
		},
	}

	starter.cs.manager.Execute(
		SERVICES().CrosToolRunner,
		CTR_SERVICE_COMMANDS().StartContainer,
		request,
	)

	go BuildServiceListener(
		&starter.cs.ServiceBase,
		false,
		exec.Command("docker", "logs", "-f", starter.cs.Name),
	)()

	return <-starter.cs.ReadyChan
}

// Stopper

type StopCacheServer struct {
	ServiceStopper
	cs *CacheServerService
}

func (stopper *StopCacheServer) Stop() error {
	if stopper.cs.Started {
		stopper.cs.CloseChan <- struct{}{}
		<-stopper.cs.CloseFinishedChan
	}

	WriteLogs(&stopper.cs.ServiceBase)

	return nil
}

// Commands
