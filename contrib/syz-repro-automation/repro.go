// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
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

var disallowedModels = map[string]bool{
	"elm": true, // elm images are not fully built
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

func processLogOpts(rootdir string, finishedBugs *os.File) (map[string]map[string][]string, error) {
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

	doneBugs := make(map[string]bool)
	scanner := bufio.NewScanner(finishedBugs)
	for scanner.Scan() {
		doneBugs[scanner.Text()] = true
	}

	modelToImageToBugs := make(map[string]map[string][]string)

	for _, bug := range logopts.Bugs {
		if _, ok := doneBugs[bug.ID]; ok {
			continue
		}
		model := bug.DUT.Model
		image := bug.DUT.ImageID
		if _, ok := disallowedModels[model]; ok {
			continue
		}
		if model != "" {
			if modelToImageToBugs[model] == nil {
				modelToImageToBugs[model] = make(map[string][]string)
			}
			bugLog := filepath.Join(rootdir, "bugs", bug.ID, "log0")
			modelToImageToBugs[model][image] = append(modelToImageToBugs[model][image], bugLog)
		}
	}

	return modelToImageToBugs, nil
}

func run(model string, minutes int, paths map[string]string, imageToBugs map[string][]string, finishedBugs *os.File) error {
	hostname, err := dut.Lease(model, minutes)
	if err != nil {
		return fmt.Errorf("error trying to lease model %v: %v", model, err)
	}
	defer dut.Abandon(hostname)

	for imageID, bugLogs := range imageToBugs {
		if err := dut.FlashKernel(hostname, imageID); err != nil {
			if imageID == "" {
				return fmt.Errorf("error flashing latest kernel: %v", err)
			}
			log.Printf("Flashing image %v failed: %v.\nTrying to flash latest image.", imageID, err)
			if err := dut.FlashKernel(hostname, ""); err != nil {
				return fmt.Errorf("error flashing latest kernel: %v", err)
			}
		}

		for _, bugLog := range bugLogs {
			// bug id is the directory name where the bug log resides
			bugID := filepath.Base(filepath.Dir(bugLog))
			log.Printf("Running syz-repro on bug %v\n...", bugID)
			if err = runSyzRepro(paths, hostname, bugLog); err != nil {
				return fmt.Errorf("error running syz-repro on bug %v: %v", bugID, err)
			} else if finishedBugs != nil {
				if _, err := finishedBugs.WriteString(bugID + "\n"); err != nil {
					return fmt.Errorf("error recording that bug %v finished reproducing: %v", bugID, err)
				}
				log.Printf("Recorded that bug %v finished reproducing\n", bugID)
			}
		}
	}

	return nil
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
		imageToBug := map[string][]string{
			*imageID: {flag.Arg(0)},
		}
		if err := run(*model, *minutes, paths, imageToBug, nil); err != nil {
			log.Panic(err)
		}
	} else {
		finishedBugsPath := filepath.Join(flag.Arg(0), "finishedbugs")
		finishedBugs, err := os.OpenFile(finishedBugsPath, os.O_APPEND|os.O_RDWR|os.O_CREATE, 0600)
		if err != nil {
			log.Panicf("error opening finishedbugs file: %v", err)
		}
		defer finishedBugs.Close()

		modelToImageToBugs, err := processLogOpts(flag.Arg(0), finishedBugs)
		if err != nil {
			log.Panic(err)
		}
		for model, imageToBugs := range modelToImageToBugs {
			if err := run(model, *minutes, paths, imageToBugs, finishedBugs); err != nil {
				log.Panicf("error on model %v: %v\n", model, err)
			}
		}
	}
}
