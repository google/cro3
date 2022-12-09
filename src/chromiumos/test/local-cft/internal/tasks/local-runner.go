// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides entry points to local cft
package tasks

import (
	"chromiumos/test/local-cft/internal/services"
	"chromiumos/test/local-cft/internal/utils"
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/maruel/subcommands"
)

const (
	RELATIVE_BASE_DIR = "local-cft"
)

// CLI command structure for running local cft
type localCftCmd struct {
	subcommands.CommandRunBase

	flagSet       *flag.FlagSet
	tests         string
	tags          string
	localServices string
	tagsExclude   string
	model         string
	board         string
	build         string
	dutHost       string
	baseDir       string
	chroot        string
	fullRun       bool
	provision     bool
	test          bool
	testFind      bool
	// publish   bool

	errorLogger *log.Logger
}

// Combines services with their relevant commands for simple execution
type serviceToRun struct {
	name    string
	service services.Service
	cmds    []services.ServiceCommand_
}

// Entrypoint for running local-cft
func LocalCft() int {
	localCft := &localCftCmd{
		flagSet: flag.NewFlagSet("cli", flag.ContinueOnError),
	}

	localCft.flagSet.StringVar(&localCft.tests, "tests", "", "test(s) to run, comma separated. Example: -tests test1,test2")
	localCft.flagSet.StringVar(&localCft.tags, "tags", "", "tag(s) to run, comma separated. Example: -tags group:1,group:2")
	localCft.flagSet.StringVar(&localCft.localServices, "localservices", "", "Services with local updates to include in containers\n Eg cros-dut,cros-test,cros-test")
	localCft.flagSet.StringVar(&localCft.tagsExclude, "tagsExclude", "", "Excluded tag(s) to run, comma separated. Example: -tags group:1,group:2")
	localCft.flagSet.StringVar(&localCft.model, "model", "", "Model name")
	localCft.flagSet.StringVar(&localCft.board, "board", "", "Board name")
	localCft.flagSet.StringVar(&localCft.build, "build", "", "Build number to run containers from.\n Eg R108 or R108-14143. Do not use with -md_path")
	localCft.flagSet.StringVar(&localCft.dutHost, "host", "", "Hostname of dut")
	localCft.flagSet.StringVar(&localCft.baseDir, "dir", "/tmp", "The base absolute path for the local-cft runner's interactions and output.\n Eg /tmp")
	localCft.flagSet.StringVar(&localCft.chroot, "chroot", "", "Absolute path of your chromiumos chroot. Necessary for updating local services.")
	localCft.flagSet.BoolVar(&localCft.fullRun, "fullrun", false, "Run the full flow of cft.\n\tWhen true, provision and test are defaulted to true")
	localCft.flagSet.BoolVar(&localCft.provision, "provision", false, "Run cros-provision")
	localCft.flagSet.BoolVar(&localCft.test, "test", false, "Run cros-test-finder and cros-test")
	localCft.flagSet.BoolVar(&localCft.testFind, "findtest", false, "Run cros-test-finder")
	// localCft.flagSet.BoolVar(&localCft.publish, "publish", false, "Run cros-publish")

	return localCft.Run()
}

// Defines the usage lines for local-cft
func (c *localCftCmd) printUsage() {
	localCftUsage := `
Usage: local-cft [OPTIONS] <argument>
	`

	println(localCftUsage)
	c.flagSet.PrintDefaults()
}

// Execution for local-cft.
// Validates the state, parses arguments,
// and computes which services will run,
// subsequently running each service and command.
func (c *localCftCmd) Run() int {
	c.errorLogger = log.New(os.Stderr, "ERROR: ", log.Ldate|log.Ltime)

	if err := c.Validate(); err != nil {
		c.errorLogger.Println(err)
		return 2
	}

	ctx := context.Background()
	parsedTests := strings.Split(c.tests, ",")
	parsedTags := strings.Split(c.tags, ",")
	parsedExcludedTags := strings.Split(c.tagsExclude, ",")
	parsedLocalServices := strings.Split(c.localServices, ",")
	c.baseDir = fmt.Sprintf("%s/%s", c.baseDir, RELATIVE_BASE_DIR)

	manager := services.NewLocalCFTManager(
		ctx,
		c.board, c.model, c.build, c.dutHost, c.baseDir, c.chroot,
		parsedTests, parsedTags, parsedExcludedTags,
		parsedLocalServices,
	)

	servicesToRun := c.compileServicesToRun(manager)

	defer func() {
		if err := manager.Stop(); err != nil {
			c.errorLogger.Println(err)
		}
	}()
	for _, serviceToRun := range servicesToRun {
		if err := manager.Start(serviceToRun.name, serviceToRun.service); err != nil {
			c.errorLogger.Printf("Failed to run %s, %s", serviceToRun.name, err)
			return 1
		}
		for _, cmd := range serviceToRun.cmds {
			if err := manager.Execute(serviceToRun.name, cmd); err != nil {
				c.errorLogger.Printf("Failed to execute %s, %s", cmd, err)
				return 1
			}
		}
	}

	return 0
}

// Uses CLI args to determine which services and commands will be run for local-cft
func (c *localCftCmd) compileServicesToRun(manager *services.LocalCFTManager) []serviceToRun {
	servicesToRun := []serviceToRun{}

	ctrService := &services.CTRService{
		ServiceBase: services.NewDefaultServiceBase(manager, services.SERVICES().CrosToolRunner),
	}
	servicesToRun = append(servicesToRun, serviceToRun{
		name:    services.SERVICES().CrosToolRunner,
		service: ctrService,
		cmds:    []services.ServiceCommand_{},
	})

	if c.fullRun {
		c.provision = true
		c.testFind = true
		c.test = true
	}

	if c.provision {
		servicesToRun = append(servicesToRun, serviceToRun{
			name: services.SERVICES().CrosProvision,
			service: &services.CrosProvisionService{
				ServiceBase: services.NewDefaultServiceBase(manager, services.SERVICES().CrosProvision),
			},
			cmds: []services.ServiceCommand_{services.CROS_PROVISION_SERVICE_COMMANDS().Install},
		})
	}
	if c.test || c.testFind {
		servicesToRun = append(servicesToRun, serviceToRun{
			name: services.SERVICES().CrosTestFinder,
			service: &services.CrosTestFinderService{
				ServiceBase: services.NewDefaultServiceBase(manager, services.SERVICES().CrosTestFinder),
			},
			cmds: []services.ServiceCommand_{services.CROS_TEST_FINDER_SERVICE_COMMANDS().FindTests},
		})
	}
	if c.test {
		servicesToRun = append(servicesToRun, serviceToRun{
			name: services.SERVICES().CrosTest,
			service: &services.CrosTestService{
				ServiceBase: services.NewDefaultServiceBase(manager, services.SERVICES().CrosTest),
			},
			cmds: []services.ServiceCommand_{services.CROS_TEST_SERVICE_COMMANDS().RunTests},
		})
	}
	// if c.publish || c.fullRun {
	// servicesToRun = append(servicesToRun, ServiceToRun{
	// 	name: services.SERVICES().CrosProvision,
	// 	service: &services.CrosProvisionService{
	// 		ServiceBase: services.NewDefaultServiceBase(manager, services.SERVICES().CrosProvision),
	// 	},
	// 	cmds: []services.ServiceCommand_{services.CROS_PROVISION_SERVICE_COMMANDS().Install},
	// })
	// }

	return servicesToRun
}

func (c *localCftCmd) validateArgs() error {
	if c.board == "" || c.model == "" {
		return fmt.Errorf("-model and -board must be provided.")
	}
	if c.dutHost == "" {
		return fmt.Errorf("-duthost must be provided.")
	}

	parsedLocalServices := strings.Split(c.localServices, ",")
	if c.localServices != "" && len(parsedLocalServices) > 0 && c.chroot == "" {
		return fmt.Errorf("Local services requires having the -chroot flag")
	}

	return nil
}

func (c *localCftCmd) checkPreReqs() error {
	if err := utils.CheckAutoSSHInstalled(); err != nil {
		return err
	}
	if err := utils.CheckDockerInstalled(); err != nil {
		return err
	}

	return nil
}

func (c *localCftCmd) Validate() error {
	if err := c.flagSet.Parse(os.Args[1:]); err != nil {
		c.printUsage()
		return fmt.Errorf("Failed to parse args, %s", err)
	}
	if err := c.validateArgs(); err != nil {
		c.printUsage()
		return fmt.Errorf("Failed to validate args, %s", err)
	}
	if err := c.checkPreReqs(); err != nil {
		return fmt.Errorf("Failed to pass prereq checks, %s", err)
	}

	return nil
}
