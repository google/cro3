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
	dutSleep    = 2 * time.Second
	flashBuffer = 20 * time.Minute
)

type leasedDut struct {
	hostname string
	model    string
	imageID  string
	expTime  time.Time
}

var currDut *leasedDut

// Get leases a DUT if the current DUT is nil, the model requested for the DUT has changed, or the DUT lease is about to expire.
// Otherwise if only the DUT imageID has changed, we will get the new image.
// If all fields are the same, Get does nothing.
// Returns the current DUT's hostname.
func Get(model, imageID string, minutes int, timeNeeded time.Duration) (string, error) {
	if currDut == nil || currDut.model != model || time.Now().Add(timeNeeded).Add(flashBuffer).After(currDut.expTime) {
		Abandon()
		hostname, err := lease(model, minutes)
		if err != nil {
			return "", err
		}
		expTime := time.Now().Add(time.Duration(minutes) * time.Minute)
		if err := getKernel(hostname, imageID); err != nil {
			abandonDut(hostname)
			return "", err
		}
		// Note imageID may not correspond to the actual image on the DUT.
		// If user given imageID does not work and second-latest image is flashed onto DUT,
		// imageID will still equal user given imageID. This way if user given imageID is present again,
		// we will not try to flash the user given imageID again, and instead use the current DUT.
		currDut = &leasedDut{
			hostname: hostname,
			model:    model,
			imageID:  imageID,
			expTime:  expTime,
		}
		return currDut.hostname, nil
	} else if currDut.imageID != imageID {
		if err := getKernel(currDut.hostname, imageID); err != nil {
			Abandon()
			return "", err
		}
		currDut.imageID = imageID
	}
	return currDut.hostname, nil
}

// lease leases a DUT of type model and for specified minutes, runs crosfleet dut lease.
// Returns leased DUT's hostname.
func lease(model string, minutes int) (string, error) {
	log.Printf("Leasing model %v device for %v minutes...\n", model, minutes)
	ret, err := cmd.RunCmd(true, "crosfleet", "dut", "lease", "-model", model, "--minutes", strconv.Itoa(minutes))
	if err != nil {
		return "", fmt.Errorf("error leasing device: %v", err)
	}

	// Prints out lease information for user.
	log.Println(ret)

	// ret looks like "Leased chromeos6-row18-rack16-host10 until 19 Jul 21 19:58 UTC".
	// Returns hostname, e.g. chromeos6-row18-rack16-host10.
	return strings.Split(ret, " ")[1] + ".cros", nil
}

func getKernel(hostname, imageID string) error {
	if err := flashKernel(hostname, imageID); err != nil {
		if imageID == "" {
			return fmt.Errorf("error flashing latest kernel: %v", err)
		}
		log.Printf("Flashing image %v failed: %v.\nTrying to flash latest image.", imageID, err)
		if err := flashKernel(hostname, ""); err != nil {
			return fmt.Errorf("error flashing latest kernel: %v", err)
		}
	}
	return nil
}

// flashKernel flashes a kernel onto the DUT at hostname, runs cros flash.
func flashKernel(hostname, imageID string) error {
	board, err := getBoard(hostname)
	if err != nil {
		return fmt.Errorf("unable to get board for DUT: %v", err)
	}
	if imageID == "" {
		log.Printf("Image id not provided, fetching second-latest image for board %v...\n", board)
		imageID, err = getSecondLatestImage(board)
		if err != nil {
			return fmt.Errorf("unable to get latest image for board: %v", err)
		}
	}
	log.Printf("Flashing kernel onto DUT...")
	ssh := "ssh://root@" + hostname
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
		"ssh",
		"-o", "UserKnownHostsFile=/dev/null",
		"-o", "BatchMode=yes",
		"-o", "IdentitiesOnly=yes",
		"-o", "StrictHostKeyChecking=no",
		"-o", "ConnectTimeout=10",
		"root@" + hostname, "pwd",
	}
	for {
		if _, err := cmd.RunCmd(false, args...); err != nil {
			log.Printf("ssh failed: %v. sleeping for %v and trying again.", err, dutSleep)
			time.Sleep(dutSleep)
		} else {
			break
		}
	}
}

func abandonDut(hostname string) {
	log.Println("Abandoning DUT at " + hostname + "...")
	ret, err := cmd.RunCmd(false, "crosfleet", "dut", "abandon", hostname)
	if err != nil {
		log.Fatal(fmt.Errorf("error abandoning DUT: %v", err))
	}
	log.Println(ret)
}

// Abandon abandons the DUT at hostname, runs crosfleet dut abandon.
func Abandon() {
	if currDut == nil {
		return
	}
	abandonDut(currDut.hostname)
	currDut = nil
}

func getSecondLatestImage(board string) (string, error) {
	bucket := "gs://chromeos-image-archive/" + board + "-debug-kernel-postsubmit"
	ret, err := cmd.RunCmd(false, "gsutil.py", "ls", bucket)
	if err != nil {
		return "", err
	}
	lines := strings.Split(ret, "\n")

	// Get third to last line as the last line is blank.
	// We get the second latest image because flashing the latest image runs into issues.
	imageLine := lines[len(lines)-3]

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
