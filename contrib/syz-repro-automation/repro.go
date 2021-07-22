// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type dutConfig struct {
	Targets       []string `json:"targets"`
	TargetDir     string   `json:"target_dir"`
	TargetReboot  bool     `json:"target_reboot"`
	StartupScript string   `json:"startup_script"`
	Pstore        bool     `json:"pstore"`
}

type syzreproConfig struct {
	Name      string    `json:"name"`
	Target    string    `json:"target"`
	Reproduce bool      `json:"reproduce"`
	HTTP      string    `json:"http"`
	Workdir   string    `json:"workdir"`
	Syzkaller string    `json:"syzkaller"`
	Type      string    `json:"type"`
	SSHKey    string    `json:"sshkey"`
	Procs     int       `json:"procs"`
	DUTConfig dutConfig `json:"vm"`
}

const (
	syzReproTimeout = 20 * time.Minute
)

func runCmd(print bool, cmdStr ...string) (string, error) {
	cmd := exec.Command(cmdStr[0], cmdStr[1:]...)
	var out bytes.Buffer
	var stderr bytes.Buffer

	cmd.Stdout = &out
	cmd.Stderr = &stderr
	if print {
		stdoutW := io.MultiWriter(&out, os.Stdout)
		stderrW := io.MultiWriter(&stderr, os.Stdout)
		cmd.Stdout = stdoutW
		cmd.Stderr = stderrW
	}
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%v: %v", err, stderr.String())
	}

	return out.String(), nil
}

func runCmdLog(outputLog string, timeout time.Duration, cmdStr ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, cmdStr[0], cmdStr[1:]...)

	outputFile, err := os.Create(outputLog)
	if err != nil {
		return err
	}
	defer outputFile.Close()

	writer := io.Writer(outputFile)
	cmd.Stdout = writer
	cmd.Stderr = writer

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("cmd error: %v, ctx err: %v", err, ctx.Err())
	}

	return nil
}

func runSyzRepro(paths map[string]string, hostname string, reproLog string) error {
	syzreproTempDir, err := ioutil.TempDir("", "syzrepro-temp")
	if err != nil {
		return fmt.Errorf("unable to create tempdir: %v", err)
	}

	workdir := filepath.Join(syzreproTempDir, "workdir")
	if err = os.Mkdir(workdir, 0775); err != nil {
		return fmt.Errorf("unable to create workdir: %v", err)
	}
	defer os.RemoveAll(syzreproTempDir)

	config := syzreproConfig{
		Name:      "syzrepro-automation",
		Target:    "linux/amd64",
		Reproduce: true,
		HTTP:      "localhost:56700",
		Workdir:   workdir,
		Syzkaller: paths["syzkaller"],
		Type:      "isolated",
		SSHKey:    paths["sshKey"],
		Procs:     1,
		DUTConfig: dutConfig{
			Targets:       []string{hostname + ".cros"},
			TargetDir:     "/tmp",
			TargetReboot:  false,
			StartupScript: paths["startupScript"],
			Pstore:        true,
		},
	}

	configPath := filepath.Join(syzreproTempDir, "config.cfg")
	configFile, err := os.Create(configPath)
	if err != nil {
		return fmt.Errorf("unable to create syzkaller configfile: %v", err)
	}
	defer configFile.Close()

	if err := json.NewEncoder(configFile).Encode(config); err != nil {
		return fmt.Errorf("invalid syzkaller configuration: %v", err)
	}

	outputLog := filepath.Join(paths["syzkaller"], "outputLog-"+time.Now().Format("2006-01-02-15:04:05"))
	log.Printf("Running syz-repro, output directed to %v\n", outputLog)
	if err = runCmdLog(outputLog, syzReproTimeout, paths["syzrepro"], "-config="+configPath, "-vv", "10", reproLog); err != nil {
		return fmt.Errorf("error running syz-repro: %v", err)
	}

	return nil
}

func abandonDut(hostname string) {
	log.Println("Abandoning DUT at " + hostname + "...")
	ret, err := runCmd(false, "crosfleet", "dut", "abandon", hostname)
	if err != nil {
		log.Fatal(fmt.Errorf("error abandoning DUT: %v", err))
	}
	log.Println(ret)
}

func getLatestImage(board string) (string, error) {
	bucket := "gs://chromeos-image-archive/" + board + "-debug-kernel-postsubmit"
	ret, err := runCmd(false, "gsutil.py", "ls", bucket)
	if err != nil {
		return "", err
	}
	lines := strings.Split(ret, "\n")

	// The last line is a blank line
	imageLine := lines[len(lines)-2]
	sections := strings.Split(imageLine, "/")

	// Line looks like gs://chromeos-image-archive/octopus-debug-kernel-postsubmit/R94-14102.0.0-51496-8841198623588369056/
	// Last element is empty
	latestImage := sections[len(sections)-2]
	log.Printf("Found latest image %v for board %v\n", latestImage, board)
	return latestImage, nil
}

func flashKernel(hostname string, imageID string) error {
	board, err := getDutBoard(hostname)
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
	if _, err = runCmd(true, "cros", "flash", "--board="+board, ssh, xBuddy); err != nil {
		return fmt.Errorf("error flashing kernel onto DUT: %v", err)
	}
	log.Printf("Finished flashing kernel onto DUT")

	return nil
}

func getDutBoard(hostname string) (string, error) {
	ret, err := runCmd(false, "crosfleet", "dut", "info", hostname)
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
	ret, err := runCmd(true, "crosfleet", "dut", "lease", "-model", model, "--minutes", strconv.Itoa(minutes))
	if err != nil {
		return "", fmt.Errorf("error leasing device: %v", err)
	}

	// prints out lease information for user
	log.Println(ret)

	// out.String() looks like "Leased chromeos6-row18-rack16-host10 until 19 Jul 21 19:58 UTC"
	// returns hostname, e.g. chromeos6-row18-rack16-host10
	return strings.Split(ret, " ")[1], nil
}

func checkPaths(paths []string) error {
	for _, path := range paths {
		if _, err := os.Stat(path); os.IsNotExist(err) {
			return fmt.Errorf("path for %v is invalid: %v", err)
		}
	}
	return nil
}

func main() {
	model := flag.String("model", "garg", "Model for leased DUT")
	minutes := flag.Int("minutes", 60, "Number of minutes to lease DUT")
	imageID := flag.String("imageid", "", "Kernel image id to flash onto DUT")

	flag.Parse()

	if flag.Arg(0) == "" {
		log.Fatal("must provide a log file to run syz-repro on")
	}

	syzkallerDir := os.Getenv("SYZKALLER")
	if syzkallerDir == "" {
		log.Fatal("environment variable SYZKALLER is not set")
	}
	syzrepro := filepath.Join(syzkallerDir, "bin", "syz-repro")
	sshKey := filepath.Join(syzkallerDir, "testing_rsa")
	startupScript := filepath.Join(syzkallerDir, "startup_script.sh")

	if err := checkPaths([]string{syzkallerDir, syzrepro, sshKey, startupScript}); err != nil {
		log.Fatal(err)
	}

	paths := map[string]string{
		"syzkaller":     syzkallerDir,
		"syzrepro":      syzrepro,
		"sshKey":        sshKey,
		"startupScript": startupScript,
	}

	hostname, err := leaseDut(*model, *minutes)
	if err != nil {
		log.Fatal(err)
	}
	defer abandonDut(hostname)

	if err = flashKernel(hostname, *imageID); err != nil {
		panic(err)
	}

	if err = runSyzRepro(paths, hostname, flag.Arg(0)); err != nil {
		panic(err)
	}
}
