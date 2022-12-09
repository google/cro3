// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package utils

import (
	"fmt"
	"log"
	"os/exec"
	"time"
)

type containerTarget struct {
	Src    string
	Dst    string
	DelDst string
}

// UpdateContainerService updates the container that will run for a given service
func UpdateContainerService(logger *log.Logger, chroot, imageBase, service string) error {
	targets := []*containerTarget{
		&containerTarget{
			Src:    fmt.Sprintf("%s/usr/bin/%s", chroot, service),
			Dst:    "usr/bin",
			DelDst: fmt.Sprintf("usr/bin/%s", service),
		},
	}

	if err := updateBinary(logger, service); err != nil {
		return err
	}

	if err := updateImage(logger, imageBase, targets, service == "cros-test-finder"); err != nil {
		return err
	}

	return nil
}

// updateBinary emerges the local changes into a binary
func updateBinary(logger *log.Logger, service string) error {
	workon := exec.Command("cros_sdk", "cros-workon", "--host", "start", service)
	if err := workon.Run(); err != nil {
		return fmt.Errorf("Workon failed, %s", err)
	}

	emerge := exec.Command("cros_sdk", "sudo", "emerge", service)
	if err := emerge.Run(); err != nil {
		return fmt.Errorf("Emerge failed. %s", err)
	}
	return nil
}

// createCleanedImage calls into the container to remove the old binary/state
func createCleanedImage(logger *log.Logger, image, tempName string, targets []*containerTarget, sudo bool) error {
	args := []string{"run", "-d", "--name", tempName, image}
	if sudo {
		args = append(args, "sudo")
	}
	args = append(args, "rm", "-r")
	for _, target := range targets {
		args = append(args, target.DelDst)
	}
	// docker run -d --name <name> <image> sudo rm -r [delDst]
	logger.Print(fmt.Sprintf("Running: docker %s", args))
	create := exec.Command("docker", args...)
	if err := create.Run(); err != nil {
		return fmt.Errorf("docker run failed for %s, %s", image, err)
	}

	return nil
}

// updateImage ensures there is a clean image, places a binary inside the image, then commits the image with the suffix "_localchange"
func updateImage(logger *log.Logger, image string, targets []*containerTarget, sudo bool) error {
	timeName := fmt.Sprint(time.Now().UnixNano())
	createCleanedImage(logger, image, timeName, targets, sudo)

	for _, target := range targets {
		if err := copyIntoDocker(logger, target, timeName); err != nil {
			logger.Println(fmt.Errorf("copy failed, will respin, %s", err))
			timeName, err = respinImage(target, timeName)
			if err != nil {
				return err
			}
			if err := copyIntoDocker(logger, target, timeName); err != nil {
				return fmt.Errorf("Failed to copy twice, %s", err)
			}
		}
	}

	logger.Println("Copy into container succeeded, committing container.")
	args := []string{"commit", timeName, image + "_localchange"}
	commit := exec.Command("docker", args...)
	if err := commit.Run(); err != nil {
		return fmt.Errorf("Failed to commit, %s", err)
	}

	return nil
}

// copyIntoDocker copies the local binary into the container based on the Dst location
func copyIntoDocker(logger *log.Logger, target *containerTarget, tempName string) error {
	args := []string{"cp", target.Src, fmt.Sprintf("%s:%s", tempName, target.Dst)}
	cp := exec.Command("docker", args...)
	if out, err := cp.Output(); err != nil {
		logger.Println(fmt.Errorf("docker cp failed, retrying, %s, %s", err, string(out)))
		cp = exec.Command("docker", args...)
		if out2, err := cp.Output(); err != nil {
			return fmt.Errorf("docker cp 2nd try failed, %s, %s", err, string(out2))
		}
	}

	return nil
}

// respinImage commits the failed image then recleans the image in the event of a flake
func respinImage(target *containerTarget, tempName string) (string, error) {
	args := []string{"commit", tempName, tempName + "_failedcopy"}
	commit := exec.Command("docker", args...)
	sha, err := commit.Output()
	if err != nil {
		return "", fmt.Errorf("Respin failed, docker commit failed, %s", err)
	}
	timeName := fmt.Sprint(time.Now().UnixNano())
	newArgs := []string{"run", "-d", "--name", timeName, string(sha), "sudo", "rm", "-r", target.DelDst}
	respin := exec.Command("docker", newArgs...)
	if err := respin.Run(); err != nil {
		return "", fmt.Errorf("Failed to respin, %s", err)
	}

	return timeName, nil
}
