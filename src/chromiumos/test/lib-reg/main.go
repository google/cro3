// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements registration for test libraries.
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"
)

const (
	servicesFile   = "services.txt"
	defaultLogPath = "/tmp/test-libs-registration.log"
)

// newLogger creates a logger - using go default logger.
func newLogger(logFile *os.File) *log.Logger {
	mw := io.MultiWriter(logFile, os.Stderr)
	return log.New(mw, "", log.LstdFlags|log.LUTC)
}

// readRegInfo parses a single library's file into a LibReg struct.
func readRegInfo(infoPath string) (*LibReg, error) {
	infoFile, err := os.Open(infoPath)
	if err != nil {
		return nil, fmt.Errorf("could not open info file: %s", err)
	}
	defer infoFile.Close()

	bytes, err := ioutil.ReadAll(infoFile)
	if err != nil {
		return nil, fmt.Errorf("could not read info file: %s", err)
	}

	reg := &LibReg{}
	err = json.Unmarshal(bytes, reg)
	if err != nil {
		return nil, fmt.Errorf("could not parse info file: %s", err)
	}

	err = reg.Validate()
	if err != nil {
		return nil, err
	}

	return reg, nil
}

// WriteRegInfo creates a JSON file referencing all valid test libraries listed
// line-by-line in servicesFile.  This JSON file is consumable by Test Libs Service.
func WriteRegInfo(srcPath, outputPath string, logger *log.Logger) error {
	// Locate src/ directory for relative file paths.
	if filepath.Base(srcPath) != "src" {
		logger.Println("Thought src/ was at", srcPath)
		return errors.New("Could not find src/ - was src-path entered correctly?")
	}

	// Read in input.
	in, err := os.Open(servicesFile)
	if err != nil {
		return fmt.Errorf("Could not open input file: %s", err)
	}
	defer in.Close()

	// Find all register-able services.
	libs := []*LibReg{}
	scanner := bufio.NewScanner(in)
	for scanner.Scan() {
		txt := scanner.Text()
		if txt == "" || strings.HasPrefix(txt, "//") {
			continue
		}
		rInfo, err := readRegInfo(filepath.Join(srcPath, txt))
		if err != nil {
			logger.Printf("Could not get service info for %s: %s", txt, err)
			continue
		}
		libs = append(libs, rInfo)
	}

	// Write output for later use.
	regsJSON, err := json.Marshal(libs)
	if err != nil {
		return fmt.Errorf("Could not marshal output JSON: %s", err)
	}
	regsJSON = append(regsJSON, byte('\n')) // Add a newline for cros lint check.
	ioutil.WriteFile(outputPath, regsJSON, 0644)
	return nil
}

func main() {
	var srcPath, outputPath, logPath string
	flag.StringVar(&srcPath, "src-path", "",
		"Path to src/ location.")
	flag.StringVar(&outputPath, "output-path", "output.json",
		"Path to output file location (will be overwritten if exists).")
	flag.StringVar(&logPath, "log-path", defaultLogPath,
		"Path to log output (also printed to stdout)")
	flag.Parse()

	logFile, err := os.Create(logPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		os.Exit(2)
	}
	defer logFile.Close()
	logger := newLogger(logFile)

	err = WriteRegInfo(srcPath, srcPath, logger)
	if err != nil {
		log.Fatalln(err)
		os.Exit(2)
	}
	return
}
