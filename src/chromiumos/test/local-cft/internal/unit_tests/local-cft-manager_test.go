// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package unit_tests

import (
	"chromiumos/test/local-cft/internal/services"
	"context"
	"reflect"
	"testing"
)

type MockServiceExecutor struct {
	services.ServiceExecutor

	Starters []reflect.Type
	Commands []reflect.Type
	Stoppers []reflect.Type
}

func (ex *MockServiceExecutor) Start(starter services.ServiceSetup) error {
	ex.Starters = append(ex.Starters, reflect.TypeOf(starter))
	return nil
}

func (ex *MockServiceExecutor) Execute(cmd services.ServiceCommand) error {
	ex.Commands = append(ex.Commands, reflect.TypeOf(cmd))
	return nil
}

func (ex *MockServiceExecutor) Stop(stopper services.ServiceStopper) error {
	ex.Stoppers = append(ex.Stoppers, reflect.TypeOf(stopper))
	return nil
}

func NewMockServiceExecutor() *MockServiceExecutor {
	return &MockServiceExecutor{
		Starters: []reflect.Type{},
		Commands: []reflect.Type{},
		Stoppers: []reflect.Type{},
	}
}

func NewMockLocalCFTManager() *services.LocalCFTManager {
	return services.NewLocalCFTManager(
		context.Background(),
		"fakeboard", "fakemodel", "fakebuild", "fakedut", "/tmp",
		[]string{}, []string{},
	)
}

func TestStart_startFullRun(t *testing.T) {
	executor := NewMockServiceExecutor()
	manager := NewMockLocalCFTManager()

	manager.Start(services.SERVICES().CrosToolRunner, &services.CTRService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosToolRunner),
	})
	manager.Start(services.SERVICES().CrosProvision, &services.CrosProvisionService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosProvision),
	})
	manager.Start(services.SERVICES().CrosTestFinder, &services.CrosTestFinderService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTestFinder),
	})
	manager.Start(services.SERVICES().CrosTest, &services.CrosTestService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTest),
	})

	expectedStarters := map[reflect.Type]int{}

	addExpected := func(t reflect.Type, count int) {
		expectedStarters[t] = count
	}

	addExpected(reflect.TypeOf(&services.SetupCTR{}), 1)
	addExpected(reflect.TypeOf(&services.SetupCacheServer{}), 1)
	addExpected(reflect.TypeOf(&services.SetupSSHTunnel{}), 2)
	addExpected(reflect.TypeOf(&services.SetupCrosDut{}), 1)
	addExpected(reflect.TypeOf(&services.SetupCrosProvision{}), 1)
	addExpected(reflect.TypeOf(&services.SetupCrosTestFinder{}), 1)
	addExpected(reflect.TypeOf(&services.SetupCrosTest{}), 1)

	for _, s := range executor.Starters {
		expectedStarters[s] -= 1
		expected := expectedStarters[s]
		if expected < 0 {
			t.Fatalf("Expected starter %s to be found", s.String())
		}
		if expected == 0 {
			delete(expectedStarters, s)
		}
	}

	if len(expectedStarters) > 0 {
		t.Log(expectedStarters)
		t.Fatalf("Failed to find all starters")
	}
}

func TestExecute_commandsRanFullRun(t *testing.T) {
	executor := NewMockServiceExecutor()
	manager := NewMockLocalCFTManager()

	manager.Start(services.SERVICES().CrosToolRunner, &services.CTRService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosToolRunner),
	})
	manager.Start(services.SERVICES().CrosProvision, &services.CrosProvisionService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosProvision),
	})
	manager.Start(services.SERVICES().CrosTestFinder, &services.CrosTestFinderService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTestFinder),
	})
	manager.Start(services.SERVICES().CrosTest, &services.CrosTestService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTest),
	})

	manager.Execute(services.SERVICES().CrosProvision, services.CROS_PROVISION_SERVICE_COMMANDS().Install)
	manager.Execute(services.SERVICES().CrosTestFinder, services.CROS_TEST_FINDER_SERVICE_COMMANDS().FindTests)
	manager.Execute(services.SERVICES().CrosTest, services.CROS_TEST_SERVICE_COMMANDS().RunTests)

	expectedCommands := map[reflect.Type]int{}

	addExpected := func(t reflect.Type, count int) {
		expectedCommands[t] = count
	}

	addExpected(reflect.TypeOf(&services.InstallCommand{}), 1)
	addExpected(reflect.TypeOf(&services.FindTestsCommand{}), 1)
	addExpected(reflect.TypeOf(&services.RunTestsCommand{}), 1)

	for _, s := range executor.Commands {
		expectedCommands[s] -= 1
		expected := expectedCommands[s]
		if expected < 0 {
			t.Fatalf("Expected command %s to be found", s.String())
		}
		if expected == 0 {
			delete(expectedCommands, s)
		}
	}

	if len(expectedCommands) > 0 {
		t.Log(expectedCommands)
		t.Fatalf("Failed to find all commands")
	}
}

func TestExecute_stopFullRun(t *testing.T) {
	executor := NewMockServiceExecutor()
	manager := NewMockLocalCFTManager()

	manager.Start(services.SERVICES().CrosToolRunner, &services.CTRService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosToolRunner),
	})
	manager.Start(services.SERVICES().CrosProvision, &services.CrosProvisionService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosProvision),
	})
	manager.Start(services.SERVICES().CrosTestFinder, &services.CrosTestFinderService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTestFinder),
	})
	manager.Start(services.SERVICES().CrosTest, &services.CrosTestService{
		ServiceBase: services.NewServiceBase(manager, executor, services.SERVICES().CrosTest),
	})

	manager.Stop()

	expectedStoppers := map[reflect.Type]int{}

	addExpected := func(t reflect.Type, count int) {
		expectedStoppers[t] = count
	}

	addExpected(reflect.TypeOf(&services.StopCTR{}), 1)
	addExpected(reflect.TypeOf(&services.StopCacheServer{}), 1)
	addExpected(reflect.TypeOf(&services.StopSSHTunnel{}), 2)
	addExpected(reflect.TypeOf(&services.StopCrosDut{}), 1)
	addExpected(reflect.TypeOf(&services.StopCrosProvision{}), 1)
	addExpected(reflect.TypeOf(&services.StopCrosTestFinder{}), 1)
	addExpected(reflect.TypeOf(&services.StopCrosTest{}), 1)

	for _, s := range executor.Stoppers {
		expectedStoppers[s] -= 1
		expected := expectedStoppers[s]
		if expected < 0 {
			t.Fatalf("Expected command %s to be found", s.String())
		}
		if expected == 0 {
			delete(expectedStoppers, s)
		}
	}

	if len(expectedStoppers) > 0 {
		t.Log(expectedStoppers)
		t.Fatalf("Failed to find all stoppers")
	}
}
