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

type crosTestFinderServiceCommands struct {
	FindTests ServiceCommand_
}

// Enum of available commands for cros-test-finder
func CROS_TEST_FINDER_SERVICE_COMMANDS() crosTestFinderServiceCommands {
	return crosTestFinderServiceCommands{
		FindTests: "find-tests",
	}
}

// Service implementation for cros-test-finder
type CrosTestFinderService struct {
	Service
	ServiceBase

	client api.TestFinderServiceClient
}

func (c *CrosTestFinderService) Start() error {
	c.Port = utils.GetFreePort()
	c.manager.ports[c.Name] = c.Port

	c.LocalLogger.Printf("Starting %s on port %d", c.Name, c.Port)

	starter := &SetupCrosTestFinder{
		ctf: c,
	}
	return c.executor.Start(starter)
}

func (c *CrosTestFinderService) Execute(commandName ServiceCommand_, args ...interface{}) error {
	var cmd ServiceCommand = nil
	switch commandName {
	case CROS_TEST_FINDER_SERVICE_COMMANDS().FindTests:
		cmd = &FindTestsCommand{
			ctf: c,
		}
	default:
		return fmt.Errorf("Command %s not found", commandName)
	}
	return c.executor.Execute(cmd)
}

func (c *CrosTestFinderService) Stop() error {
	stopper := &StopCrosTestFinder{
		ctf: c,
	}
	return c.executor.Stop(stopper)
}

// Setup

type SetupCrosTestFinder struct {
	ServiceSetup
	ctf *CrosTestFinderService
}

func (starter *SetupCrosTestFinder) Setup() error {
	if err := utils.EnsureContainerAvailable(starter.ctf.Name); err != nil {
		err := fmt.Errorf("Failed to ensure container %s was available, %s", starter.ctf.Name, err)
		starter.ctf.LocalLogger.Println(err)
		return err
	}

	request := &api.StartContainerRequest{
		Name: starter.ctf.Name,
		ContainerImage: fmt.Sprintf(
			"us-docker.pkg.dev/cros-registry/test-services/%s:%s",
			starter.ctf.Name,
			starter.ctf.manager.images[starter.ctf.Name].Tags[0],
		),
		AdditionalOptions: &api.StartContainerRequest_Options{
			Expose:  []string{fmt.Sprint(starter.ctf.Port)},
			Network: "host",
		},
		StartCommand: []string{
			"cros-test-finder",
			"server",
			"-port",
			fmt.Sprint(starter.ctf.Port),
		},
	}

	starter.ctf.manager.Execute(
		SERVICES().CrosToolRunner,
		CTR_SERVICE_COMMANDS().StartContainer,
		request,
	)

	go BuildServiceListener(
		&starter.ctf.ServiceBase,
		false,
		exec.Command("docker", "logs", "-f", starter.ctf.Name),
	)()

	if err := <-starter.ctf.ReadyChan; err != nil {
		starter.ctf.LocalLogger.Println(err)
		return err
	}

	if err := BuildConnection(&starter.ctf.ServiceBase); err != nil {
		return err
	}
	starter.ctf.client = api.NewTestFinderServiceClient(starter.ctf.conn)

	return nil
}

// Stopper

type StopCrosTestFinder struct {
	ServiceStopper
	ctf *CrosTestFinderService
}

func (stopper *StopCrosTestFinder) Stop() error {
	if stopper.ctf.conn != nil {
		stopper.ctf.conn.Close()
	}

	stopper.ctf.CloseChan <- struct{}{}
	<-stopper.ctf.CloseFinishedChan

	WriteLogs(&stopper.ctf.ServiceBase)

	return nil
}

// Commands

type FindTestsCommand struct {
	ServiceCommand
	ctf *CrosTestFinderService
}

func (cmd *FindTestsCommand) Execute() error {
	testSuites := []*api.TestSuite{}
	var tags []string = nil
	var tagsExclude []string = nil
	if len(cmd.ctf.manager.Tags) > 0 && cmd.ctf.manager.Tags[0] != "" {
		tags = cmd.ctf.manager.Tags
	}
	if len(cmd.ctf.manager.TagsExclude) > 0 && cmd.ctf.manager.TagsExclude[0] != "" {
		tagsExclude = cmd.ctf.manager.TagsExclude
	}
	if tags != nil || tagsExclude != nil {
		testSuites = append(testSuites, &api.TestSuite{
			Spec: &api.TestSuite_TestCaseTagCriteria_{
				TestCaseTagCriteria: &api.TestSuite_TestCaseTagCriteria{
					Tags:        tags,
					TagExcludes: tagsExclude,
				},
			},
		})
	}

	testCaseIds := []*api.TestCase_Id{}
	for _, testCaseId := range cmd.ctf.manager.Tests {
		if testCaseId != "" {
			testCaseIds = append(testCaseIds, &api.TestCase_Id{
				Value: testCaseId,
			})
		}
	}

	if len(testCaseIds) > 0 {
		testSuites = append(testSuites, &api.TestSuite{
			Spec: &api.TestSuite_TestCaseIds{
				TestCaseIds: &api.TestCaseIdList{
					TestCaseIds: testCaseIds,
				},
			},
		})
	}

	findTestsRequest := &api.CrosTestFinderRequest{
		TestSuites: testSuites,
	}

	findTestResult, err := cmd.ctf.client.FindTests(cmd.ctf.manager.ctx, findTestsRequest)
	if err != nil {
		return fmt.Errorf("Failed to find tests, %s", err)
	}
	cmd.ctf.manager.testSuites = findTestResult.TestSuites
	for _, testSuite := range findTestResult.TestSuites {
		cmd.ctf.LocalLogger.Printf("Found %d tests:\n", len(testSuite.GetTestCases().TestCases))
		cmd.ctf.LocalLogger.Printf("%v\n", testSuite.GetTestCases().TestCases)
	}

	return nil
}
