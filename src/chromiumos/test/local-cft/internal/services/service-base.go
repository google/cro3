// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"bytes"
	"fmt"
	"io"
	"log"
	"strings"

	"google.golang.org/grpc"
)

// Represents how to start up a service
type ServiceSetup interface {
	Setup() error
}

// Represents the implementation of a command being called within a service
type ServiceCommand interface {
	Execute() error
}

// Represents the implementation for how to stop a service
type ServiceStopper interface {
	Stop() error
}

// Service Command type alias
type ServiceCommand_ = string

// Service represents the required functions for Service structures
type Service interface {
	// Sets up and runs the Service
	Start() error

	// Runs an implemented command on the Service
	Execute(ServiceCommand_, ...interface{}) error

	// Shutdowns the service and cleans up
	Stop() error
}

// Base structure of Service implementations.
// Contains common variables used across implementations
type ServiceBase struct {
	manager  *LocalCFTManager
	executor ServiceExecutor

	Name    string
	Port    uint16
	BaseDir string
	Started bool

	ReadyChan         chan error
	CloseChan         chan struct{}
	CloseFinishedChan chan struct{}

	LocalLogger   *log.Logger
	ServiceLogger *log.Logger
	loggerBuf     *bytes.Buffer

	conn *grpc.ClientConn
}

type ServiceResult_ = string
type ServiceResult struct {
	Undefined ServiceResult_
	Success   ServiceResult_
	Failed    ServiceResult_
}

// SERVICE_RESULT provides possibilities for service result
func SERVICE_RESULT() ServiceResult {
	return ServiceResult{
		Undefined: "UNDEFINED",
		Success:   "SUCCESS",
		Failed:    "FAILED",
	}
}

// example-service -> EXAMPLE_SERVICE
func kebabToUpperSnake(in string) (out string) {
	parts := strings.Split(strings.ToUpper(in), "-")
	out = strings.Join(parts, "_")
	return
}

// Provides uniform construction of base services
func NewServiceBase(
	manager *LocalCFTManager,
	executor ServiceExecutor,
	name string,
) ServiceBase {
	buffer := new(bytes.Buffer)
	multiwriter := io.MultiWriter(log.Default().Writer(), buffer)

	return ServiceBase{
		manager:           manager,
		executor:          executor,
		Name:              name,
		BaseDir:           manager.BaseDir,
		ReadyChan:         make(chan error),
		CloseChan:         make(chan struct{}),
		CloseFinishedChan: make(chan struct{}),
		Started:           false,
		loggerBuf:         buffer,
		LocalLogger:       log.New(multiwriter, fmt.Sprintf("%s (local):   ", kebabToUpperSnake(name)), log.Ldate|log.Ltime|log.Lshortfile),
		ServiceLogger:     log.New(multiwriter, fmt.Sprintf("%s (service): ", kebabToUpperSnake(name)), 0),
	}
}

// Provides a ServiceBase constructed with the DefaultServiceExecutor
func NewDefaultServiceBase(
	manager *LocalCFTManager,
	name string,
) ServiceBase {
	return NewServiceBase(
		manager,
		&DefaultServiceExecutor{},
		name,
	)
}

// ServiceExecutor represents how the service should handle its execution requests
type ServiceExecutor interface {
	Start(ServiceSetup) error
	Execute(ServiceCommand) error
	Stop(ServiceStopper) error
}

type DefaultServiceExecutor struct {
	ServiceExecutor
}

func (c *DefaultServiceExecutor) Start(starter ServiceSetup) error {
	return starter.Setup()
}

func (c *DefaultServiceExecutor) Execute(cmd ServiceCommand) error {
	return cmd.Execute()
}

func (c *DefaultServiceExecutor) Stop(stopper ServiceStopper) error {
	return stopper.Stop()
}
