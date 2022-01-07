// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the cros-servod for starting/stopping servod daemon
// and sending commands to it to control and test DUTs via servo hardware by
// simulating user actions such as power on/off, flashing of firmware/OS,
// screen close, etc.
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"chromiumos/test/servod/cmd/commandexecutor"
	"chromiumos/test/servod/cmd/model"
	"chromiumos/test/servod/cmd/servodserver"

	"go.chromium.org/luci/common/errors"
)

const (
	// version is the version info of this command. It is filled in during emerge.
	version         = "<unknown>"
	helpDescription = `cros-servod tool

The tool provides the ability to start/stop a servod Docker container either on the same host or a remote servo host and execute servod commands on it.
go/cros-servod-design to learn more about the design.

Commands:
  cli       Runs the server in CLI mode, executes one of the subcommands (start_servod, stop_servod, exec_cmd, call_servod) by using the input parameters and prints the result to the output file.
            Usage:
            To start servod:
            cros-servod cli start_servod --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --servod_docker_image_path <servod_docker_image_path> --servod_port <servod_port> --board <board> --model <model> --serial_name <serial_name> --debug <debug> --recovery_mode <recovery_mode> --config <config> --allow_dual_v4 <allow_dual_v4> [--log_path /tmp/servod/]

            To stop servod:
            cros-servod cli stop_servod --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --servod_port <servod_port> [--log_path /tmp/servod/]

            To execute command:
            cros-servod cli exec_cmd --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --command <command> [--log_path /tmp/servod/]

            To call servod for doc:
            cros-servod cli call_servod --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --method doc [--log_path /tmp/servod/]

            To call servod for get:
            cros-servod cli call_servod --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --method get --args <args> [--log_path /tmp/servod/]

            To call servod for set:
            cros-servod cli call_servod --servo_host_path <ip:port> --servod_docker_container_name <a_unique_name> --method set --args <args> [--log_path /tmp/servod/]

  server    Starts the servod server for RPC calls. Mostly used for tests.
            Usage:
            cros-servod server [--log_path /tmp/servod/] [--server_port 80]

  --version Prints the version.
  
  --help    Prints the help.`
	defaultLogDirectory = "/tmp/servod/"
	defaultServerPort   = 80
	defaultServodPort   = 9999
)

// createLogFile creates a file and its parent directory for logging purpose.
func createLogFile(logPath string) (*os.File, error) {
	t := time.Now()
	fullPath := filepath.Join(logPath, t.Format("20060102-150405"))
	if err := os.MkdirAll(fullPath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create directory %v: %v", fullPath, err)
	}

	logFullPathName := filepath.Join(fullPath, "log.txt")

	// Log the full output of the command to disk.
	logFile, err := os.Create(logFullPathName)
	if err != nil {
		return nil, fmt.Errorf("failed to create file %v: %v", fullPath, err)
	}
	return logFile, nil
}

// newLogger creates a logger. Using go default logger for now.
func newLogger(logFile *os.File) *log.Logger {
	mw := io.MultiWriter(logFile, os.Stderr)
	return log.New(mw, "", log.LstdFlags|log.LUTC)
}

func runCLI(ctx context.Context, cs model.CliSubcommand, d []string) int {
	a := model.CliArgs{}
	fs := flag.NewFlagSet("Run servod", flag.ExitOnError)
	fs.StringVar(&a.LogPath, "log_path", defaultLogDirectory, fmt.Sprintf("Path to record execution logs. The default value is %s", defaultLogDirectory))
	fs.StringVar(&a.ServoHostPath, "servo_host_path", "", "The path (URI) for the servod (containerized or running as a daemon) host.")
	fs.StringVar(&a.ServodDockerContainerName, "servod_docker_container_name", "", "The servod Docker container name.")
	fs.StringVar(&a.ServodDockerImagePath, "servod_docker_image_path", "", "The servod Docker image path to pull from GCR.")
	var servodPort int
	fs.IntVar(&servodPort, "servod_port", defaultServodPort, fmt.Sprintf("The --PORT parameter value for servod command. The default value is %d.", defaultServodPort))
	fs.StringVar(&a.Board, "board", "", "The --BOARD parameter value for servod command.")
	fs.StringVar(&a.Model, "model", "", "The --MODEL parameter value for servod command.")
	fs.StringVar(&a.SerialName, "serial_name", "", "The --SERIALNAME parameter value for servod command.")
	fs.StringVar(&a.Debug, "debug", "", "The --DEBUG parameter value for servod command.")
	fs.StringVar(&a.RecoveryMode, "recovery_mode", "", "The --RECOVERY_MODE parameter value for servod command.")
	fs.StringVar(&a.Config, "config", "", "The --CONFIG parameter value for servod command.")
	fs.StringVar(&a.AllowDualV4, "allow_dual_v4", "", "The --ALLOW-DUAL-V4 parameter value for servod command.")
	fs.StringVar(&a.Command, "command", "", "The command to execute inside the servod Docker container.")
	fs.StringVar(&a.Method, "method", "", "The method to call. Accepted values are doc, get, and set.")
	fs.StringVar(&a.Args, "args", "", "The arguments to pass to the method.")
	fs.Parse(d)
	a.ServodPort = int32(servodPort)

	logFile, err := createLogFile(a.LogPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	commandexecutor := commandexecutor.NewServodCommandExecutor(logger)

	servodService, destructor, err := servodserver.NewServodService(ctx, logger, commandexecutor)
	defer destructor()
	if err != nil {
		logger.Fatalln("Failed to create servod service: ", err)
		return 2
	}

	if _, _, err := servodService.RunCli(cs, a, nil, true); err != nil {
		logger.Fatalln("Failed to run CLI: ", err)
		return 1
	}
	return 0
}

func startServer(ctx context.Context, d []string) int {
	a := model.CliArgs{}
	fs := flag.NewFlagSet("Start servod server", flag.ExitOnError)
	fs.StringVar(&a.LogPath, "log_path", defaultLogDirectory, fmt.Sprintf("The path to record execution logs. The default value is %s", defaultLogDirectory))
	var serverPort int
	fs.IntVar(&serverPort, "server_port", defaultServerPort, fmt.Sprintf("The port for the servod GRPC server. The default value is %d.", defaultServerPort))
	fs.Parse(d)
	a.ServerPort = int32(serverPort)

	logFile, err := createLogFile(a.LogPath)
	if err != nil {
		log.Fatalln("Failed to create log file", err)
		return 2
	}
	defer logFile.Close()

	logger := newLogger(logFile)
	commandexecutor := commandexecutor.NewServodCommandExecutor(logger)

	servodService, destructor, err := servodserver.NewServodService(ctx, logger, commandexecutor)
	defer destructor()
	if err != nil {
		logger.Fatalln("Failed to create servod service: ", err)
		return 2
	}

	if err := servodService.StartServer(a.ServerPort); err != nil {
		logger.Fatalln("Failed to start servod server: ", err)
		return 1
	}
	return 0
}

// Specify run mode for cros-servod.
type runMode string

const (
	runCli     runMode = "cli"
	runServer  runMode = "server"
	runVersion runMode = "version"
	runHelp    runMode = "help"
)

func getRunMode() (runMode, error) {
	if len(os.Args) > 1 {
		for _, a := range os.Args {
			if a == "--version" {
				return runVersion, nil
			}
		}
		switch strings.ToLower(os.Args[1]) {
		case "cli":
			return runCli, nil
		case "server":
			return runServer, nil
		}
	}
	// If we did not find special run mode then just print help for user.
	return runHelp, nil
}

func getCliSubcommand() (model.CliSubcommand, error) {
	if len(os.Args) > 2 {
		switch strings.ToLower(os.Args[2]) {
		case "start_servod":
			return model.CliStartServod, nil
		case "stop_servod":
			return model.CliStopServod, nil
		case "exec_cmd":
			return model.CliExecCmd, nil
		case "call_servod":
			return model.CliCallServod, nil
		}
	}
	return model.CliUnknown, errors.Reason("Unknown CLI subcommand").Err()
}

func mainInternal() int {
	rm, err := getRunMode()
	if err != nil {
		log.Fatalln(err)
		return 2
	}

	ctx := context.Background()
	switch rm {
	case runCli:
		log.Printf("Running CLI mode!")
		cs, err := getCliSubcommand()
		if err != nil {
			log.Fatalln(err)
			return 2
		}
		return runCLI(ctx, cs, os.Args[3:])
	case runServer:
		log.Printf("Running server mode!")
		return startServer(ctx, os.Args[2:])
	case runVersion:
		log.Printf("cros-servod version: %s", version)
		return 0
	}

	log.Println(helpDescription)
	return 0
}

func main() {
	os.Exit(mainInternal())
}
