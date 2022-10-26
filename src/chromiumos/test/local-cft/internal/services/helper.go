// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides service implementations and management
package services

import (
	"bufio"
	"fmt"
	"io/ioutil"
	"net"
	"os"
	"os/exec"
	"time"

	"google.golang.org/grpc"
)

const (
	// OWNER: Execute, Read, Write
	// GROUP: Execute, Read
	// OTHER: Execute, Read
	DIR_PERMISSION = 0755

	// OWNER: Read, Write
	// GROUP: Read
	// OTHER: Read
	FILE_PERMISSION = 0644

	LOGS_PATH = "output"
)

// Builds a listener function that connects to the service through a specified OS command.
// Once connected, logs all output of the service, and sends out a signal that the service
// is ready to be used. Finally, waits to receive signal to shutdown.
func BuildServiceListener(service *ServiceBase, skipDial bool, cmd *exec.Cmd) func() {
	return func() {
		outReader, err := cmd.StdoutPipe()
		if err != nil {
			service.ReadyChan <- err
		}
		cmd.Stderr = cmd.Stdout
		defer outReader.Close()

		outScanner := bufio.NewScanner(outReader)

		go func() {
			if !skipDial {
				for st := time.Now(); time.Now().Sub(st) < time.Second*10; time.Sleep(time.Millisecond * 250) {
					conn, innerErr := net.Dial("tcp", fmt.Sprintf("localhost:%d", service.Port))
					err = innerErr
					if err == nil {
						conn.Close()
						break
					}
				}
			}

			if err != nil {
				service.ReadyChan <- fmt.Errorf("Failed to start %s, %s", service.Name, err)
			}

			service.ReadyChan <- nil

			for outScanner.Scan() {
				line := outScanner.Text()
				service.ServiceLogger.Println(line)
			}
		}()

		if err = cmd.Start(); err != nil {
			service.ReadyChan <- fmt.Errorf("Failed to listen to %s, %s", service.Name, err)
		}

		go func() {
			<-service.CloseChan
			if err = cmd.Process.Signal(os.Interrupt); err != nil {
				service.LocalLogger.Printf("Failed to stop %s, %s\n", service.Name, err)
			}
		}()

		cmd.Wait()
		service.CloseFinishedChan <- struct{}{}
	}
}

// Creates a connection to the service
func BuildConnection(service *ServiceBase) error {
	conn, err := grpc.Dial(fmt.Sprintf("localhost:%d", service.Port), grpc.WithInsecure())
	if err != nil {
		return fmt.Errorf("Failed to establish connection to %s, %s", service.Name, err)
	}
	service.conn = conn

	return nil
}

// Dumps the logs compiled over the service's lifetime into an output directory
func WriteLogs(service *ServiceBase) {
	if err := os.MkdirAll(fmt.Sprintf("%s/%s/", service.BaseDir, LOGS_PATH), DIR_PERMISSION); err != nil {
		service.LocalLogger.Printf("Failed to create output directory, %s\n", err)
	}

	if err := ioutil.WriteFile(fmt.Sprintf("%s/%s/%s.log", service.BaseDir, LOGS_PATH, service.Name), service.loggerBuf.Bytes(), FILE_PERMISSION); err != nil {
		service.LocalLogger.Printf("Failed to write %s output to file, %s\n", service.Name, err)
	}
}
