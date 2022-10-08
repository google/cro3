// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Responsible for the abstraction layer representing each command grouping
package cli

import (
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
)

// AbstractCommand represents a CLI grouping (e.g.: run as server, run as CLI, etc)
type AbstractCommand interface {
	// Run runs the command
	Run() error

	// Is checks if the string is representative of the command
	Is(string) bool

	// Init is an initializer for the command given the trailing args
	Init([]string) error

	// Name is the command name (for debugging)
	Name() string
}

// SetUpLog sets up the logging for the CLI
func SetUpLog(dir string) (*log.Logger, error) {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create directory %v: %v", dir, err)
	}
	lfp := filepath.Join(dir, "log.txt")
	lf, err := os.Create(lfp)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %v: %v", lfp, err)
	}
	newLog := log.New(io.MultiWriter(lf, os.Stderr), "<lacros-provision>", log.LstdFlags|log.LUTC)
	newLog.SetFlags(log.LstdFlags | log.Lshortfile | log.Lmsgprefix)
	return newLog, nil
}

// ParseInputs is a helper method which parses input arguments. It is
// effectively a factory method.
func ParseInputs() (AbstractCommand, error) {
	if len(os.Args) < 1 {
		return nil, errors.New("CLI arguments must be specified")
	}

	cmds := []AbstractCommand{
		NewServerCommand(),
		NewCLICommand(),
	}

	subcommand := os.Args[1]
	options := []string{}

	for _, cmd := range cmds {
		options = append(options, cmd.Name())
		if cmd.Is(subcommand) {
			if err := cmd.Init(os.Args[2:]); err != nil {
				return nil, fmt.Errorf("failed to initialize cli command, %s", err)
			}
			return cmd, nil
		}
	}

	return nil, fmt.Errorf("Unknown subcommand: %s. \nOptions are: [%s]", subcommand, options)

}
