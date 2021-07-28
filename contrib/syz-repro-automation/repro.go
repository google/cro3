// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/google/syz-repro-automation/cmd"
	"github.com/google/syz-repro-automation/dut"
	"gopkg.in/yaml.v2"
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

type dutObj struct {
	Model   string `yaml:"model"`
	ImageID string `yaml:"imageid"`
}

type bug struct {
	ID  string `yaml:"id"`
	DUT dutObj `yaml:"dut"`
}

type logOpts struct {
	Bugs []bug `yaml:"bugs"`
}

const (
	syzReproTimeout = 20 * time.Minute
)

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

	dut.WaitForDut(hostname)

	outputLog := filepath.Join(filepath.Dir(reproLog), "outputLog-"+time.Now().Format("2006-01-02-15:04:05"))
	log.Printf("Running syz-repro, output directed to %v\n", outputLog)
	if err = cmd.RunCmdLog(outputLog, syzReproTimeout, paths["syzrepro"], "-config="+configPath, "-vv", "10", reproLog); err != nil {
		return fmt.Errorf("error running syz-repro: %v", err)
	}

	return nil
}

func checkPaths(paths []string) error {
	for _, path := range paths {
		if _, err := os.Stat(path); os.IsNotExist(err) {
			return fmt.Errorf("filepath %v is invalid: %v", err)
		}
	}
	return nil
}

func processLogOpts(rootdir string) (map[dutObj][]string, error) {
	logoptsFile := filepath.Join(rootdir, "logopts.yaml")
	yamlFile, err := ioutil.ReadFile(logoptsFile)
	if err != nil {
		return nil, fmt.Errorf("unable to read logopts.yaml file: %v", err)
	}

	logopts := logOpts{}
	err = yaml.Unmarshal(yamlFile, &logopts)
	if err != nil {
		return nil, fmt.Errorf("unable to unmarshal logopts.yaml: %v", err)
	}

	dutToBugs := make(map[dutObj][]string)

	for _, bug := range logopts.Bugs {
		if bug.DUT.Model != "" {
			dutToBugs[bug.DUT] = append(dutToBugs[bug.DUT], bug.ID)
		}
	}

	return dutToBugs, nil
}

func run(model string, minutes int, imageID string, paths map[string]string, bugLogs []string) {
	hostname, err := dut.Lease(model, minutes)
	if err != nil {
		log.Fatal(err)
	}
	defer dut.Abandon(hostname)

	if err = dut.FlashKernel(hostname, imageID); err != nil {
		log.Panic(err)
	}

	for _, bugLog := range bugLogs {
		if err = runSyzRepro(paths, hostname, bugLog); err != nil {
			log.Panic(err)
		}
	}
}

func main() {
	model := flag.String("model", "garg", "Model for leased DUT")
	minutes := flag.Int("minutes", 60, "Number of minutes to lease DUT")
	imageID := flag.String("imageid", "", "Kernel image id to flash onto DUT")
	logFile := flag.Bool("logfile", false, "Argument supplied is a log file")
	logDir := flag.Bool("logdir", false, "Argument supplied is a directory")

	flag.Parse()

	if *logFile == *logDir {
		log.Fatal("please use exactly one of the flags -logfile or -dir")
	}

	if flag.Arg(0) == "" {
		log.Fatal("must provide a file or directory to run syz-repro on")
	}

	syzkallerDir := os.Getenv("SYZKALLER")
	if syzkallerDir == "" {
		log.Fatal("environment variable SYZKALLER is not set")
	}
	syzrepro := filepath.Join(syzkallerDir, "bin", "syz-repro")
	sshKey := filepath.Join(syzkallerDir, "testing_rsa")
	startupScript := filepath.Join(syzkallerDir, "startup_script.sh")

	if err := checkPaths([]string{flag.Arg(0), syzkallerDir, syzrepro, sshKey, startupScript}); err != nil {
		log.Fatal(err)
	}

	paths := map[string]string{
		"syzkaller":     syzkallerDir,
		"syzrepro":      syzrepro,
		"sshKey":        sshKey,
		"startupScript": startupScript,
	}

	if *logFile {
		run(*model, *minutes, *imageID, paths, []string{flag.Arg(0)})
	} else {
		dutToBugs, err := processLogOpts(flag.Arg(0))
		if err != nil {
			log.Panic(err)
		}
		for dut, bugIDs := range dutToBugs {
			var bugLogs []string
			for _, bugID := range bugIDs {
				bugLogs = append(bugLogs, filepath.Join(flag.Arg(0), "bugs", bugID, "log0"))
			}
			run(dut.Model, *minutes, dut.ImageID, paths, bugLogs)
		}
	}
}
