// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"context"
	"fmt"

	buildapi "go.chromium.org/chromiumos/config/go/build/api"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// LocalCFTManager acts as the middle man between the CLI args
// and the concrete management of the services being run.
// Handles knowledge of which services are running, as well as
// how to start, stop, and pass commands to services.
type LocalCFTManager struct {
	services        map[string]Service
	servicesStarted []string
	ports           map[string]uint16
	ctx             context.Context

	Board       string
	Model       string
	Build       string
	Tests       []string
	Tags        []string
	TagsExclude []string
	DutHost     string
	BaseDir     string

	imagePath    string
	images       map[string]*buildapi.ContainerImageInfo
	testSuites   []*api.TestSuite
	testResponse *api.CrosTestResponse
}

type services struct {
	CrosToolRunner   string
	CrosProvision    string
	CrosDut          string
	CrosTest         string
	CrosTestFinder   string
	CacheServer      string
	SSHTunnel        string
	SSHReverseTunnel string
}

// Enum of defined runnable services
func SERVICES() services {
	return services{
		CrosToolRunner:   "cros-tool-runner",
		CrosProvision:    "cros-provision",
		CrosDut:          "cros-dut",
		CrosTest:         "cros-test",
		CrosTestFinder:   "cros-test-finder",
		CacheServer:      "cache-server",
		SSHTunnel:        "ssh-tunnel",
		SSHReverseTunnel: "ssh-reverse-tunnel",
	}
}

// Initializes a LocalCFTManager
func NewLocalCFTManager(
	ctx context.Context,
	board, model, build, dutHost, baseDir string,
	tests, tags, tagsExclude []string,
) *LocalCFTManager {
	return &LocalCFTManager{
		ctx:             ctx,
		services:        make(map[string]Service),
		servicesStarted: []string{},
		ports:           make(map[string]uint16),
		images:          make(map[string]*buildapi.ContainerImageInfo),
		Board:           board,
		Model:           model,
		Build:           build,
		DutHost:         dutHost,
		BaseDir:         baseDir,
		Tests:           tests,
		Tags:            tags,
		TagsExclude:     tagsExclude,
		imagePath:       "",
	}
}

// Calls the service to start then logs the service as running
func (c *LocalCFTManager) Start(serviceName string, service Service) error {
	c.services[serviceName] = service
	c.servicesStarted = append([]string{serviceName}, c.servicesStarted...)
	return c.services[serviceName].Start()
}

// Passes the command to the specified service
func (c *LocalCFTManager) Execute(serviceName, commandName ServiceCommand_, args ...interface{}) error {
	return c.services[serviceName].Execute(commandName, args)
}

// Stops all services that are running in the reverse order of when they started
func (c *LocalCFTManager) Stop() (err error) {
	for _, service := range c.servicesStarted {
		if innerErr := c.services[service].Stop(); innerErr != nil {
			err = fmt.Errorf("%s, %s", innerErr, err)
		}
		delete(c.services, service)
	}
	c.servicesStarted = []string{}

	return
}
