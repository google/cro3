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

	flag.Parse()

	hostname, err := leaseDut(*model, *minutes)
	if err != nil {
		log.Fatal(err)
	}

	log.Println(hostname)
}
