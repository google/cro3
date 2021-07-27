// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/google/syz-repro-automation/cmd"
)

const (
	dutSleep = 2 * time.Second
)

// Lease leases a DUT of type model and for specified minutes, runs crosfleet dut lease.
// Returns leased DUT's hostname.
func Lease(model string, minutes int) (string, error) {
	log.Printf("Leasing model %v device for %v minutes...\n", model, minutes)
	ret, err := cmd.RunCmd(true, "crosfleet", "dut", "lease", "-model", model, "--minutes", strconv.Itoa(minutes))
	if err != nil {
		return "", fmt.Errorf("error leasing device: %v", err)
	}

	// Prints out lease information for user.
	log.Println(ret)

	// ret looks like "Leased chromeos6-row18-rack16-host10 until 19 Jul 21 19:58 UTC".
	// Returns hostname, e.g. chromeos6-row18-rack16-host10.
	return strings.Split(ret, " ")[1], nil
}

// FlashKernel flashes a kernel onto the DUT at hostname, runs cros flash.
func FlashKernel(hostname string, imageID string) error {
	board, err := getBoard(hostname)
	if err != nil {
		return err
	}
	if imageID == "" {
		log.Printf("Image id not provided, fetching latest image for board %v...\n", board)
		imageID, err = getLatestImage(board)
		if err != nil {
			return err
		}
	}
	log.Printf("Flashing kernel onto DUT...")
	ssh := "ssh://root@" + hostname + ".cros"
	xBuddy := "xBuddy://remote/" + board + "-debug-kernel-postsubmit/" + imageID
	if _, err = cmd.RunCmd(true, "cros", "flash", "--board="+board, ssh, xBuddy); err != nil {
		return fmt.Errorf("error flashing kernel onto DUT: %v", err)
	}
	log.Printf("Finished flashing kernel onto DUT")

	return nil
}

// WaitForDut checks if the DUT is up.
func WaitForDut(hostname string) {
	log.Println("Pinging DUT at " + hostname + "...")
	args := []string{
		"ssh", "root@" + hostname + ".cros", "pwd",
		"-o", "UserKnownHostsFile=/dev/null",
		"-o", "BatchMode=yes",
		"-o", "IdentitiesOnly=yes",
		"-o", "StrictHostKeyChecking=no",
		"-o", "ConnectTimeout=10",
	}
	for {
		if _, err := cmd.RunCmd(false, args...); err != nil {
			log.Printf("ssh failed: %v. sleeping for %v and trying again.", hostname, err, dutSleep)
			time.Sleep(dutSleep)
		} else {
			break
		}
	}
}

// Abandon abandons the DUT at hostname, runs crosfleet dut abandon.
func Abandon(hostname string) {
	log.Println("Abandoning DUT at " + hostname + "...")
	ret, err := cmd.RunCmd(false, "crosfleet", "dut", "abandon", hostname)
	if err != nil {
		log.Fatal(fmt.Errorf("error abandoning DUT: %v", err))
	}
	log.Println(ret)
}

func getLatestImage(board string) (string, error) {
	bucket := "gs://chromeos-image-archive/" + board + "-debug-kernel-postsubmit"
	ret, err := cmd.RunCmd(false, "gsutil.py", "ls", bucket)
	if err != nil {
		return "", err
	}
	lines := strings.Split(ret, "\n")

	// Get second to last line as the last line is blank.
	imageLine := lines[len(lines)-2]

	// imageLine looks like gs://chromeos-image-archive/octopus-debug-kernel-postsubmit/R94-14102.0.0-51496-8841198623588369056/.
	sections := strings.Split(imageLine, "/")

	// Get second to last line as the last line is blank.
	latestImage := sections[len(sections)-2]
	log.Printf("Found latest image %v for board %v\n", latestImage, board)
	return latestImage, nil
}

func getBoard(hostname string) (string, error) {
	ret, err := cmd.RunCmd(false, "crosfleet", "dut", "info", hostname)
	if err != nil {
		return "", fmt.Errorf("error getting dut info: %v", err)
	}

	/* ret looks like:
	DUT_HOSTNAME=chromeos6-row18-rack16-host4.cros
	MODEL=garg
	BOARD=octopus
	SERVO_HOSTNAME=chromeos6-row17-rack16-labstation1
	SERVO_PORT=9985
	SERVO_SERIAL=G1911051544 */
	lines := strings.Split(ret, "\n")
	return strings.Split(lines[2], "=")[1], nil
}
