// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package cmd defines the CLI for cros_openwrt_image_builder.
//
// The cros_openwrt_image_builder CLI relies on the Cobra framework. See the
// Cobra documentation for more details on how to configure a Cobra CLI.
//
// Most CLI arguments are global and most subcommands run varying build steps,
// all defined in CrosOpenWrtImageBuilder.
package cmd
