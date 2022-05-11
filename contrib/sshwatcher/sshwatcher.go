// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// To run:
// `go run sshwatcher.go host port host port host port`
// to keep ssh connection to host with local port forwarded to port 22.
//
// An example:
// `go run sshwatcher.go cheeps 2226 eve 2227 kukui 2228 rammus 2229`
//
// Your ssh config needs to be set up such that interactive password input is
// not always required. For DUTs this means use of testing_rsa key. See
// https://chromium.googlesource.com/chromiumos/docs/+/HEAD/tips-and-tricks.md#how-to-avoid-typing-test0000-or-any-password-on-ssh_ing-to-your-device

package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

func getLsbReleaseMap(hostname string) (map[string]string, error) {
	sshResult, err := exec.Command("ssh", hostname, "cat /etc/lsb-release").Output()
	if err != nil {
		return nil, err
	}
	scanner := bufio.NewScanner(strings.NewReader(string(sshResult)))
	result := map[string]string{}
	for scanner.Scan() {
		line := scanner.Text()
		p := strings.Split(line, "=")
		if len(p) != 2 {
			return nil, fmt.Errorf("unexpected format: %q", line)
		}
		result[p[0]] = p[1]
	}
	return result, nil
}

func getOsVersion(host string) (string, string, error) {
	lsbRelease, err := getLsbReleaseMap(host)
	if err != nil {
		return "", "", err
	}
	return lsbRelease["CHROMEOS_RELEASE_VERSION"], lsbRelease["CHROMEOS_ARC_VERSION"], nil
}

// For command-line parameter which holds a pair of host name and port number.
type hostPortPair struct {
	host string
	port int
}

// For sending down the chan for showing per-host status message.
type messageType struct {
	host string
	m    string
}

// Format string for the per-host status.
var fmtString string

func sshConnectionLoop(param hostPortPair, message chan messageType) {
	const waitBetweenSSHTries = 1 * time.Second
	const sleepCommand = "sleep 8h" // Command to run on remote host to keep connection.

	for {
		message <- messageType{
			host: param.host,
			m:    fmt.Sprintf("%-10v\t %-7v\t try connecting", param.host, param.port),
		}
		osVersion, arcVersion, err := getOsVersion(param.host)
		if err != nil {
			time.Sleep(waitBetweenSSHTries)
			// try again.
			continue
		}
		message <- messageType{
			host: param.host,
			m: fmt.Sprintf(fmtString,
				param.host, param.port, osVersion, arcVersion),
		}
		err = exec.Command("ssh", fmt.Sprintf("-L%v:localhost:22", param.port), param.host,
			sleepCommand).Run()
		message <- messageType{
			host: param.host,
			m:    fmt.Sprintf("%-10v\t %-7v\t disconnected with %v", param.host, param.port, err),
		}
		time.Sleep(waitBetweenSSHTries)
	}
}

func main() {
	hostArgs := os.Args[1:]
	params := []hostPortPair{}

	if len(hostArgs)%2 != 0 {
		log.Fatal("Please specify host and port pairs, the number of arguments (%v) should be even.",
			len(hostArgs))
	}
	maxHostLen := 10
	for i := 0; i < len(hostArgs); i = i + 2 {
		port, err := strconv.Atoi(hostArgs[i+1])
		if err != nil {
			log.Fatal("%v is not a number, give me a port number", hostArgs[i+1])
		}

		params = append(params, hostPortPair{
			port: port,
			host: hostArgs[i],
		})

		if len(hostArgs[i]) > maxHostLen {
			maxHostLen = len(hostArgs[i])
		}
	}
	fmtString = fmt.Sprintf("%%-%dv\t %%-7v\t%%-30v%%-26v", maxHostLen)

	message := make(chan messageType)

	for _, param := range params {
		// Try connecting once. On the way set host name to what you would expect instead of localhost.
		log.Printf("Try pre-connecting %v", param.host)
		c := exec.Command("ssh", param.host, "uname", "-a")
		c.Stderr = os.Stderr
		if sshResult, err := c.Output(); err != nil {
			log.Fatalf("host[%v] message[%v] err[%v]: can't get uname -a on remote host", param.host, string(sshResult), err)
		}
		go sshConnectionLoop(param, message)
	}

	// Now the goroutines are busy reconnecting to ssh, I can wait for their
	// messages in channel to print out status.
	status := make(map[string]string)
	const ansiClearScreen = "\x1B[2J" // ANSI escape code CSI + 2J command for clearing screen.
	for {
		msg := <-message
		status[msg.host] = msg.m

		// Clear screen before displaying
		fmt.Printf("%v", ansiClearScreen)
		fmt.Printf(fmtString+"\n",
			"host", "port", "CrOS version", "ARC version")
		for _, param := range params {
			// Clear until end of line and print status.
			fmt.Printf("%v\n", status[param.host])
		}
	}
}
