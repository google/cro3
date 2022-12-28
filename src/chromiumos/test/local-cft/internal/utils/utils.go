// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Provides utilities for local-cft
package utils

import (
	"fmt"
	"log"
	"net"
	"os/exec"
	"strings"
)

// Shutdowns any docker container with the specified name
// to ensure that the name is available for use
func EnsureContainerAvailable(containerName string) error {
	stop := exec.Command("docker", "stop", containerName)

	stopOutput, err := stop.CombinedOutput()
	output := string(stopOutput)
	if err != nil && output != fmt.Sprintf("Error response from daemon: No such container: %s\n", containerName) {
		return fmt.Errorf(output)
	}

	if strings.Contains(output, containerName) {
		return nil
	} else {
		return fmt.Errorf("Unexpected output while trying to stop container %s, %s", containerName, output)
	}
}

// Finds an available port on the running OS
// to prevent collisions between services
func GetFreePort() uint16 {
	l, err := net.Listen("tcp", ":0")
	defer l.Close()
	if err != nil {
		log.Fatalf("Failed to get port, %s", err)
	}

	return uint16(l.Addr().(*net.TCPAddr).Port)
}

// Ensure that the program 'autossh' is installed on the OS
func CheckAutoSSHInstalled() error {
	return checkAppInstalled("autossh")
}

// Ensure that the program 'docker' is installed on the OS
// and that the device can reach the docker images storage
func CheckDockerInstalled() error {
	if err := checkAppInstalled("docker"); err != nil {
		return err
	}

	testDocker := exec.Command("gcloud", "artifacts", "docker", "images", "list", "us-docker.pkg.dev/cros-registry/test-services/cros-test", "--limit", "1")
	testDockerOut, err := testDocker.CombinedOutput()
	if err != nil || testDocker.ProcessState.ExitCode() == 1 {
		if strings.Contains(string(testDockerOut), "invalid_grant: Bad Request") {
			return fmt.Errorf("Docker not authd. Please run: \n\tgcloud auth configure-docker us-docker.pkg.dev\nThen try again.")
		}
		return fmt.Errorf("Unexpected output during docker's authentication, %s, %s", string(testDockerOut), err)
	}

	return nil
}

// Helper function for checking whether an application
// exists on system
func checkAppInstalled(appName string) error {
	app := exec.Command("which", appName)
	appOut, err := app.Output()
	if err != nil {
		return fmt.Errorf("error while checking if %s was installed, %s", appName, err)
	}

	if string(appOut) == "" {
		return fmt.Errorf("%s not found. Install the application then try again.", appName)
	}

	return nil
}
