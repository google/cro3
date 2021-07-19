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

func flashKernel(hostname string, imageId string) error {
	board, err := getDutBoard(hostname)
	if err != nil {
		return err
	}
	cmd := exec.Command("cros", "flash", "--board="+board, "ssh://root@"+hostname+".cros",
		"xBuddy://remote/"+board+"-debug-kernel-postsubmit/"+imageId)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr

	log.Printf("Flashing kernel onto DUT...")
	err = cmd.Run()
	if err != nil {
		return fmt.Errorf("error flashing kernel onto DUT: %v: %v", err, stderr.String())
	}
	log.Printf("Finished flashing kernel onto DUT")

	return nil
}

func getDutBoard(hostname string) (string, error) {
	cmd := exec.Command("crosfleet", "dut", "info", hostname)
	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr

	err := cmd.Run()
	if err != nil {
		return "", fmt.Errorf("error getting dut info: %v: %v", err, stderr.String())
	}

	/* out.String() looks like:
	DUT_HOSTNAME=chromeos6-row18-rack16-host4.cros
	MODEL=garg
	BOARD=octopus
	SERVO_HOSTNAME=chromeos6-row17-rack16-labstation1
	SERVO_PORT=9985
	SERVO_SERIAL=G1911051544 */
	lines := strings.Split(out.String(), "\n")
	return strings.Split(lines[2], "=")[1], nil
}

func leaseDut(model string, minutes int) (string, error) {
	cmd := exec.Command("crosfleet", "dut", "lease", "-model", model, "--minutes", strconv.Itoa(minutes))
	var out bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &stderr

	log.Printf("Leasing model %v device for %v minutes...\n", model, minutes)
	err := cmd.Run()
	if err != nil {
		return "", fmt.Errorf("error leasing device: %v: %v", err, stderr.String())
	}

	// prints out lease information for user
	log.Println(out.String())

	// out.String() looks like "Leased chromeos6-row18-rack16-host10 until 19 Jul 21 19:58 UTC"
	// returns hostname, e.g. chromeos6-row18-rack16-host10
	return strings.Split(out.String(), " ")[1], nil
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

	err = flashKernel(hostname, *imageId)
	if err != nil {
		log.Fatal(err)
	}
}
