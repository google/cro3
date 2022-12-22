// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"math"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"

	"chromiumos/platform/dev/contrib/labtunnel/crosfleet"
	"chromiumos/platform/dev/contrib/labtunnel/fileutils"
	clog "chromiumos/platform/dev/contrib/labtunnel/log"
	"chromiumos/platform/dev/contrib/labtunnel/ssh"
)

const (
	crosfleetHostnamePrefix = "crossk-"
	crosHostnameSuffix      = ".cros"
)

var satlabHostnameMatcher = regexp.MustCompile("^satlab-(\\w+)-.*$")
var satlabIDToHostnameMapping = map[string]string{
	"0wgatfqi22088083": "chromeos1-row2-rack1-satlab",
	"0wgatfqi22088022": "chromeos1-row2-rack2-satlab",
	"0wgatfqi22088036": "chromeos1-row2-rack3-satlab",
}

const satlabUsername = "moblab"

// resolveDutHostname remove any prefixes if hostname is given, otherwise if
// hostname is "leased" will determine a host to use from crosfleet. Returns
// hostname as a string, boolean which is true if DUT is leased, and error if
// any problems determining DUT from crosfleet.
func resolveDutHostname(ctx context.Context, hostnameParam string) (string, bool, error) {
	if hostnameParam != "leased" {
		return resolveHostname(hostnameParam, ""), false, nil
	}
	hostnames, err := crosfleet.CrosfleetLeasedDUTs(ctx)
	if err != nil {
		return "", true, err
	}
	if len(hostnames) < 1 {
		return "", true, fmt.Errorf("could not find any DUTs leased from crosfleet")
	} else if len(hostnames) == 1 {
		clog.Logger.Printf("Defaulting to only leased DUT: %s", hostnames[0])
		return hostnames[0], true, nil
	}
	hostname, err := promptUserForDutChoice(ctx, hostnames)
	return hostname, true, err
}

func promptUserForDutChoice(ctx context.Context, hostnames []string) (string, error) {
	totalDuts := len(hostnames)
	prompt := fmt.Sprintf("Found %d leased DUTs please select the DUT you would like to tunnel to:\n", totalDuts)
	for i, hostname := range hostnames {
		prompt += fmt.Sprintf("%d: %s\n", i, hostname)
	}
	prompt += fmt.Sprintf("\nSelect from 0-%d: ", totalDuts-1)
	inputReader := bufio.NewReader(fileutils.NewContextualReaderWrapper(ctx, os.Stdin))
	for true {
		var selected int
		fmt.Print(prompt)
		input, err := inputReader.ReadString('\n')
		if err != nil {
			return "", fmt.Errorf("failed to read user input for prompt: %w", err)
		}
		n, err := fmt.Sscanf(input, "%d", &selected)
		if n != 1 || err != nil {
			continue
		}
		if selected >= totalDuts || selected < 0 {
			fmt.Printf("\nInvalid index %d\n\n", selected)
			selected = -1
			continue
		}
		clog.Logger.Printf("Using user selected leased DUT: %s", hostnames[selected])
		return hostnames[selected], nil
	}
	return "", fmt.Errorf("no host selected")
}

func resolveHostname(hostnameParam string, suffixToAdd string) string {
	// Remove any crosfleet name prefix.
	if strings.HasPrefix(hostnameParam, crosfleetHostnamePrefix) {
		hostnameParam = strings.TrimPrefix(hostnameParam, crosfleetHostnamePrefix)
	}
	if suffixToAdd != "" {
		// Add suffix, keeping any existing cros suffix.
		if strings.HasSuffix(hostnameParam, crosHostnameSuffix) {
			hostnameParam = strings.TrimSuffix(hostnameParam, crosHostnameSuffix)
			hostnameParam += suffixToAdd
			hostnameParam += crosHostnameSuffix
		} else {
			hostnameParam += suffixToAdd
		}
	}
	return hostnameParam
}

func buildSshManager() *ssh.ConcurrentSshManager {
	return ssh.NewConcurrentSshManager(ssh.NewRunner(sshOptions), time.Duration(sshRetryDelaySeconds)*time.Second)
}

func nextLocalPort(ctx context.Context) int {
	for true {
		localPort := localPortStart
		localPortStart++
		available, err := isPortAvailable(ctx, localPort)
		if err != nil {
			panic(fmt.Errorf("failed to find next available open port, err: %v", err))
		}
		if available {
			return localPort
		}
	}
	return -1
}

func tunnelLocalPortToRemotePort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelName string, remoteHost string, remotePort int, sshHost string) (string, error) {
	localPort := nextLocalPort(ctx)
	listenHost := fmt.Sprintf("localhost:%d", localPort)
	if remoteHost == "" {
		remoteHost = "localhost"
	}
	if satlabDroneHostOverride != "" || isSatlabHost(sshHost) {
		if remoteHost != "localhost" {
			return "", fmt.Errorf("tunneling to a non-localhost port through a satlab device is not supported")
		}
		var satlabDroneHost string
		if satlabDroneHostOverride != "" {
			satlabDroneHost = satlabDroneHostOverride

		} else {
			var err error
			satlabDroneHost, err = buildSatlabHostname(sshHost)
			if err != nil {
				return "", fmt.Errorf("failed to parse satlab hostnames from ssh host %q: %w", sshHost, err)
			}
		}
		if !strings.Contains(satlabDroneHost, "@") {
			satlabDroneHost = fmt.Sprintf("%s@%s", satlabUsername, satlabDroneHost)
		}
		remoteHost = sshHost
		sshHost = satlabDroneHost
	}
	description := fmt.Sprintf("TUNNEL-%-10s [%s -> %s -> %s:%d]", tunnelName, listenHost, sshHost, remoteHost, remotePort)
	sshManager.Ssh(ctx, true, description, func(ctx context.Context, r *ssh.Runner) error {
		return r.TunnelLocalPortToRemotePort(ctx, localPort, remoteHost, remotePort, sshHost)
	})
	return listenHost, nil
}

func isSatlabHost(hostname string) bool {
	return satlabHostnameMatcher.MatchString(hostname)
}

func buildSatlabHostname(satlabDeviceHostname string) (string, error) {
	matches := satlabHostnameMatcher.FindAllStringSubmatch(satlabDeviceHostname, -1)
	if len(matches) != 1 || len(matches[0]) != 2 {
		return "", fmt.Errorf("failed to parse satlab drone host and local device host from satlab device hostname %q", satlabDeviceHostname)
	}
	satlabID := matches[0][1]
	// TODO(b/277986050): Deterministically deduce satlab done hostnames.
	satlabDroneHost, ok := satlabIDToHostnameMapping[satlabID]
	if !ok {
		return "", fmt.Errorf("unmapped satlab hostname for satlab with ID %q", satlabID)
	}
	return satlabDroneHost, nil
}

func isPortAvailable(ctx context.Context, port int) (bool, error) {
	ssCmd := exec.CommandContext(ctx, "ss", "-tuln")
	output, err := ssCmd.Output()
	if err != nil {
		return false, fmt.Errorf("failed to check port %d is available with command %q", port, ssCmd.String())
	}
	outputLines := strings.Split(string(output), "\n")
	for _, line := range outputLines {
		fields := strings.Fields(line)
		if len(fields) < 5 || (fields[0] != "tcp" && fields[0] != "udp") {
			continue
		}
		addressParts := strings.Split(fields[4], ":")
		usedPort, err := strconv.Atoi(addressParts[len(addressParts)-1])
		if err != nil {
			continue
		}
		if usedPort == port {
			return false, nil
		}
	}
	return true, nil
}

func runContextualCommand(ctx context.Context, logPrefix string, command string, args ...string) {
	// Build cmd and ensure subprocesses are grouped.
	cmd := exec.CommandContext(ctx, command, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid:   true,
		Pdeathsig: syscall.SIGKILL,
	}

	// Log StdOut and StdErr with a prefix.
	cmdLogger := clog.NewLogger(logPrefix)
	logWriter := clog.NewWriter(cmdLogger)
	cmd.Stdout = logWriter
	cmd.Stderr = logWriter

	// Wait until the command completes or the context is cancelled.
	runChan := make(chan error)
	var runErr error
	go func() {
		runChan <- cmd.Run()
	}()
	select {
	case <-ctx.Done():
		runErr = ctx.Err()
		break
	case runErr = <-runChan:
		break
	}

	if runErr != nil && ctx.Err() != nil {
		clog.Logger.Printf("Error running command %q: %v", command, runErr)
	}

	// Silently kill any subprocesses.
	if cmd.Process != nil {
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
}

func tunnelToDut(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("DUT-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToRouter(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("ROUTER-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToPcap(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("PCAP-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToBtpeer(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("BTPEER-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToChameleon(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("CHAMELEON-", tunnelID), "", remotePortChameleond, hostname)
}

func genericTunnelToSshPort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("SSH-", tunnelID), "", remotePortSsh, hostname)
}

func genericTunnelToChameleondPort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) (string, error) {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("CHAMELEOND-", tunnelID), "", remotePortChameleond, hostname)
}

func tunnelToRoutersUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, routerCount int) ([]string, error) {
	if routerCount < 1 {
		return nil, nil
	}
	var localHostnames []string
	var localHostname string
	var err error
	localHostname, err = tunnelToRouter(ctx, sshManager, 1, resolveHostname(hostDut, "-router"))
	if err != nil {
		return nil, err
	}
	localHostnames = append(localHostnames, localHostname)
	for i := 2; i <= routerCount; i++ {
		localHostname, err = tunnelToRouter(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-router%d", i)))
		if err != nil {
			return nil, err
		}
		localHostnames = append(localHostnames, localHostname)
	}
	return localHostnames, err
}

func tunnelToPcapsUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, pcapCount int) ([]string, error) {
	if pcapCount < 1 {
		return nil, nil
	}
	var localHostnames []string
	var localHostname string
	var err error
	localHostname, err = tunnelToPcap(ctx, sshManager, 1, resolveHostname(hostDut, "-pcap"))
	if err != nil {
		return nil, err
	}
	localHostnames = append(localHostnames, localHostname)
	for i := 2; i <= pcapCount; i++ {
		localHostname, err = tunnelToPcap(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-pcap%d", i)))
		if err != nil {
			return nil, err
		}
		localHostnames = append(localHostnames, localHostname)
	}
	return localHostnames, nil
}

func tunnelToBtpeersUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, btPeerCount int) ([]string, error) {
	if btPeerCount < 1 {
		return nil, nil
	}
	var localHostnames []string
	var localHostname string
	var err error
	for i := 1; i <= btPeerCount; i++ {
		localHostname, err = tunnelToBtpeer(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-btpeer%d", i)))
		if err != nil {
			return nil, err
		}
		localHostnames = append(localHostnames, localHostname)
	}
	return localHostnames, nil
}

func tunnelToChameleonUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, tunnelID int) (string, error) {
	return tunnelToChameleon(ctx, sshManager, tunnelID, resolveHostname(hostDut, "-chameleon"))
}

func pollDUTLease(ctx context.Context, hostDut string) context.Context {
	remain, err := crosfleet.DUTLeaseTimeRemainingSeconds(ctx, hostDut)
	if err != nil {
		clog.Logger.Printf("unable to determine lease info for %s, labtunnel will run until stopped", hostDut)
		return ctx
	}
	clog.Logger.Printf("found lease for %s, labtunnel will close in %d minutes or if lease is abandoned", hostDut, remain/60)
	ctx, cancel := context.WithCancel(ctx)
	// goroutine to cancel context when lease is expired or abandoned
	go func() {
		for true {
			remain, err := crosfleet.DUTLeaseTimeRemainingSeconds(ctx, hostDut)
			if err == nil && remain == 0 {
				clog.Logger.Printf("lease ended closing tunnels")
				cancel()
				return
			}
			// poll every 60 seconds or wait remaining time on lease whichever is less
			timerSecs := int(math.Min(float64(remain), 60))
			t := time.NewTimer(time.Duration(timerSecs) * time.Second)
			select {
			case <-t.C:
				// poll again after timer expires
			case <-ctx.Done():
				return
			}
		}
	}()
	return ctx
}
