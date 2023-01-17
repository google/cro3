// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
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

func resolveDutHostname(ctx context.Context, hostnameParam string) (string, error) {
	if hostnameParam != "leased" {
		return resolveHostname(hostnameParam, ""), nil
	}
	hostnames, err := crosfleet.CrosfleetLeasedDUTs(ctx)
	if err != nil {
		return "", err
	}
	if len(hostnames) < 1 {
		return "", fmt.Errorf("could not find any DUTs leased from crosfleet")
	} else if len(hostnames) == 1 {
		clog.Logger.Printf("Defaulting to only leased DUT: %s", hostnames[0])
		return hostnames[0], nil
	}
	return promptUserForDutChoice(ctx, hostnames)
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

func tunnelLocalPortToRemotePort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelName string, remoteHost string, remotePort int, sshHost string) string {
	localPort := nextLocalPort(ctx)
	if remoteHost == "" {
		remoteHost = "localhost"
	}
	description := fmt.Sprintf("TUNNEL-%-10s [localhost:%d -> %s -> %s:%d]", tunnelName, localPort, sshHost, remoteHost, remotePort)
	sshManager.Ssh(ctx, true, description, func(ctx context.Context, r *ssh.Runner) error {
		return r.TunnelLocalPortToRemotePort(ctx, localPort, remoteHost, remotePort, sshHost)
	})
	return fmt.Sprintf("localhost:%d", localPort)
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

func tunnelToDut(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("DUT-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToRouter(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("ROUTER-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToPcap(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("PCAP-", tunnelID), "", remotePortSsh, hostname)
}

func tunnelToBtpeer(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("BTPEER-", tunnelID), "", chameleondTunnelPort(), hostname)
}

func tunnelToChameleon(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("CHAMELEON-", tunnelID), "", chameleondTunnelPort(), hostname)
}

func genericTunnelToSshPort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("SSH-", tunnelID), "", remotePortSsh, hostname)
}

func genericTunnelToChameleondPort(ctx context.Context, sshManager *ssh.ConcurrentSshManager, tunnelID int, hostname string) string {
	return tunnelLocalPortToRemotePort(ctx, sshManager, fmt.Sprint("CHAMELEOND-", tunnelID), "", remotePortChameleond, hostname)
}

func chameleondTunnelPort() int {
	if forAutotest {
		return remotePortSsh
	}
	return remotePortChameleond
}

func tunnelToRoutersUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, routerCount int) []string {
	if routerCount < 1 {
		return nil
	}
	var localHostnames []string
	localHostnames = append(localHostnames, tunnelToRouter(ctx, sshManager, 1, resolveHostname(hostDut, "-router")))
	for i := 2; i <= routerCount; i++ {
		localHostnames = append(localHostnames, tunnelToRouter(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-router%d", i))))
	}
	return localHostnames
}

func tunnelToPcapsUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, pcapCount int) []string {
	if pcapCount < 1 {
		return nil
	}
	var localHostnames []string
	localHostnames = append(localHostnames, tunnelToPcap(ctx, sshManager, 1, resolveHostname(hostDut, "-pcap")))
	for i := 2; i <= pcapCount; i++ {
		localHostnames = append(localHostnames, tunnelToPcap(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-pcap%d", i))))
	}
	return localHostnames
}

func tunnelToBtpeersUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, btPeerCount int) []string {
	if btPeerCount < 1 {
		return nil
	}
	var localHostnames []string
	for i := 1; i <= btPeerCount; i++ {
		localHostnames = append(localHostnames, tunnelToBtpeer(ctx, sshManager, i, resolveHostname(hostDut, fmt.Sprintf("-btpeer%d", i))))
	}
	return localHostnames
}

func tunnelToChameleonUsingDutHost(ctx context.Context, sshManager *ssh.ConcurrentSshManager, hostDut string, tunnelID int) string {
	return tunnelToChameleon(ctx, sshManager, tunnelID, resolveHostname(hostDut, "-chameleon"))
}
