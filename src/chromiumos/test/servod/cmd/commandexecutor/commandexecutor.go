// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commandexecutor

import (
	"bytes"
	"io"
)

// This interface allows to execute a command either locally or on a remote server.
type CommandExecutorInterface interface {
	Run(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error)
}
