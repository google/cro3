// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

type CliArgs struct {
	// Common input params.
	// Local log file path.
	LogPath string

	// The path (URI) for the servod (containerized or running as a daemon) host.
	// If cros-servod and docker-servod live on the same host, this parameter
	// should be empty.
	ServoHostPath string

	// The servod Docker container name.
	ServodDockerContainerName string

	// The servod Docker image path to pull from GCR.
	// Example: gcr.io/chromeos-bot/servod@sha256:2d25f6313c7bbac349607
	ServodDockerImagePath string

	// The --PORT parameter value for servod command.
	ServodPort int32

	// The --BOARD parameter value for servod command.
	Board string

	// The --MODEL parameter value for servod command.
	Model string

	// The --SERIALNAME parameter value for servod command.
	SerialName string

	// The --DEBUG parameter value for servod command.
	Debug string

	// The --RECOVERY_MODE parameter value for servod command.
	RecoveryMode string

	// The --CONFIG parameter value for servod command.
	Config string

	// The --ALLOW-DUAL-V4 parameter value for servod command.
	AllowDualV4 string

	// The command to execute inside the servod Docker container.
	Command string

	// The method to call. Accepted values are doc, get, and set.
	Method string

	// The arguments to pass to the method. For the doc and get methods,
	// there will be a single argument, which is the control name (e.g.
	// cli --method get --args fakedisconnect). For the set method,
	// it will be the control name and the value separated with a colon
	// and wrapped inside a quote (e.g.
	// cli --method set --args “fakedisconnect:100 2000”).
	Args string

	// The port for the servod GRPC server.
	ServerPort int32
}

// Subcommand for cli.
type CliSubcommand string

const (
	CliUnknown     CliSubcommand = ""
	CliStartServod CliSubcommand = "start_servod"
	CliStopServod  CliSubcommand = "stop_servod"
	CliExecCmd     CliSubcommand = "exec_cmd"
	CliCallServod  CliSubcommand = "call_servod"
)
