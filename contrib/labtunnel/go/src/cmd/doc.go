// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package cmd configures the labtunnel CLI.
//
// The labtunnel CLI relies on the Cobra framework. See the Cobra documentation
// for more details on how to configure a Cobra CLI.
//
// The root.go file configures the base labtunnel command. The common.go file
// includes utility functions used by multiple commands. Every other file in
// this package configures a different subcommand of the labtunnel CLI.
package cmd
