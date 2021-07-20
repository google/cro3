// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"flag"
	"fmt"
	"log"
	"os/exec"
	"strconv"
	"strings"
)

func runCmd(cmdStr ...string) (string, error) {
	cmd := exec.Command(cmdStr[0], cmdStr[1:]...)
	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%v: %v", err, stderr.String())
	}

	return out.String(), nil
}

func abandonDut(hostname string) {
	log.Println("Abandoning DUT at " + hostname + "...")
	ret, err := runCmd("crosfleet", "dut", "abandon", hostname)
	if err != nil {
		log.Fatal(fmt.Errorf("error abandoning DUT: %v", err))
	}
	log.Println(ret)
}

func flashKernel(hostname string, imageId string) error {
	board, err := getDutBoard(hostname)
	if err != nil {
		return err
	}
	log.Printf("Flashing kernel onto DUT...")
	ssh := "ssh://root@" + hostname + ".cros"
	xBuddy := "xBuddy://remote/" + board + "-debug-kernel-postsubmit/" + imageId
	if _, err = runCmd("cros", "flash", "--board="+board, ssh, xBuddy); err != nil {
		return fmt.Errorf("error flashing kernel onto DUT: %v", err)
	}
	log.Printf("Finished flashing kernel onto DUT")

	return nil
}

func getDutBoard(hostname string) (string, error) {
	ret, err := runCmd("crosfleet", "dut", "info", hostname)
	if err != nil {
		return "", fmt.Errorf("error getting dut info: %v", err)
	}

	/* out.String() looks like:
	DUT_HOSTNAME=chromeos6-row18-rack16-host4.cros
	MODEL=garg
	BOARD=octopus
	SERVO_HOSTNAME=chromeos6-row17-rack16-labstation1
	SERVO_PORT=9985
	SERVO_SERIAL=G1911051544 */
	lines := strings.Split(ret, "\n")
	return strings.Split(lines[2], "=")[1], nil
}

func leaseDut(model string, minutes int) (string, error) {
	log.Printf("Leasing model %v device for %v minutes...\n", model, minutes)
	ret, err := runCmd("crosfleet", "dut", "lease", "-model", model, "--minutes", strconv.Itoa(minutes))
	if err != nil {
		return "", fmt.Errorf("error leasing device: %v", err)
	}

	// prints out lease information for user
	log.Println(ret)

	// out.String() looks like "Leased chromeos6-row18-rack16-host10 until 19 Jul 21 19:58 UTC"
	// returns hostname, e.g. chromeos6-row18-rack16-host10
	return strings.Split(ret, " ")[1], nil
}

func main() {
	model := flag.String("model", "garg", "Model for leased DUT")
	minutes := flag.Int("minutes", 60, "Number of minutes to lease DUT")
	imageId := flag.String("imageid", "R93-14027.0.0-49783-8844471042827170672", "Kernel image id to flash onto DUT")

	flag.Parse()

	hostname, err := leaseDut(*model, *minutes)
	if err != nil {
		log.Fatal(err)
	}
	defer abandonDut(hostname)

	err = flashKernel(hostname, *imageId)
	if err != nil {
		panic(err)
	}
}
