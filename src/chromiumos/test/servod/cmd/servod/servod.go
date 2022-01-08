// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package servod provides functions to manage connection and communication with servod daemon on servo-host.
package servod

import (
	"chromiumos/test/servod/cmd/ssh"
	"chromiumos/test/servod/cmd/xmlrpc"
	"context"
	"fmt"
	"log"
	"net"
	"strconv"
	"strings"
	"time"

	xmlrpc_value "go.chromium.org/chromiumos/config/go/api/test/xmlrpc"
	"go.chromium.org/luci/common/errors"

	"infra/libs/sshpool"
)

const (
	// Waiting 60 seconds when starting servod daemon.
	startServodTimeout = 60
	// Waiting 3 seconds when stopping servod daemon.
	stopServodTimeout = 3
	// GPIO control for USB device on servo-host
	ImageUsbkeyDev = "image_usbkey_dev"
	// GPIO control for USB multiplexer
	ImageUsbkeyDirection = "image_usbkey_direction"
	// GPIO control value that causes USB drive to be attached to DUT.
	ImageUsbkeyTowardsDUT = "dut_sees_usbkey"
)

// status of servod daemon on servo-host.
type status string

const (
	servodUndefined  status = "UNDEFINED"
	servodRunning    status = "RUNNING"
	servodStopping   status = "STOPPING"
	servodNotRunning status = "NOT_RUNNING"
)

// servod holds information to manage servod daemon.
type servod struct {
	// Servo-host hostname or IP address where servod daemon will be running.
	host string
	// Port allocated for running servod.
	port int32
	// Function to receive parameters to start servod.
	getParams func() ([]string, error)
	// Proxy offers forward tunnel connections via SSH to the servod instance on Servo-Host.
	// Labs are restricted to SSH connection and port 22.
	proxy *proxy
}

// Prepare prepares servod before call it to run commands.
// If servod is running: do nothing.
// If servod is not running: start servod.
func (s *servod) Prepare(ctx context.Context, pool *sshpool.Pool) error {
	stat, err := s.getStatus(ctx, pool)
	if err != nil {
		return errors.Annotate(err, "prepare servod").Err()
	}
	switch stat {
	case servodNotRunning:
		err = s.start(ctx, pool)
		if err != nil {
			return errors.Annotate(err, "prepare servod").Err()
		}
		return nil
	case servodRunning:
		return nil
	}
	return errors.Reason("prepare servod %s:%d: fail to start", s.host, s.port).Err()
}

// getStatus return status of servod daemon on the servo-host.
func (s *servod) getStatus(ctx context.Context, pool *sshpool.Pool) (status, error) {
	r := ssh.Run(ctx, pool, s.host, fmt.Sprintf("status servod PORT=%d", s.port))
	if r.ExitCode == 0 {
		if strings.Contains(strings.ToLower(r.Stdout), "start/running") {
			return servodRunning, nil
		} else if strings.Contains(strings.ToLower(r.Stdout), "stop/waiting") {
			return servodStopping, nil
		}
	} else if strings.Contains(strings.ToLower(r.Stderr), "unknown instance") {
		return servodNotRunning, nil
	}
	log.Println(ctx, "Status check: %s", r.Stderr)
	return servodUndefined, errors.Reason("servo status %q: fail to check status", s.host).Err()
}

// start starts servod daemon on servo-host.
func (s *servod) start(ctx context.Context, pool *sshpool.Pool) error {
	params, err := s.getParams()
	if err != nil {
		return errors.Annotate(err, "start servod").Err()
	}
	cmd := strings.Join(append([]string{"start", "servod"}, params...), " ")
	r := ssh.Run(ctx, pool, s.host, cmd)
	if r.ExitCode != 0 {
		return errors.Reason("start servod: %s", r.Stderr).Err()
	}
	// Waiting to start servod.
	// TODO(otabek@): Replace to use servod tool to wait servod start.
	log.Println(ctx, "Start servod: waiting %d seconds to initialize daemon.", startServodTimeout)
	time.Sleep(startServodTimeout * time.Second)
	return nil
}

// Stop stops servod daemon on servo-host.
func (s *servod) Stop(ctx context.Context, pool *sshpool.Pool) error {
	r := ssh.Run(ctx, pool, s.host, fmt.Sprintf("stop servod PORT=%d", s.port))
	if r.ExitCode != 0 {
		log.Println(ctx, "stop servod: %s", r.Stderr)
		return errors.Reason("stop servod: %s", r.Stderr).Err()
	} else {
		// Wait to teardown the servod.
		log.Println(ctx, "Stop servod: waiting %d seconds to fully teardown the daemon.", stopServodTimeout)
		time.Sleep(stopServodTimeout * time.Second)
	}
	return nil
}

// Call performs execution commands by servod daemon by XMLRPC connection.
func (s *servod) Call(ctx context.Context, pool *sshpool.Pool, method string, args []*xmlrpc_value.Value) (r *xmlrpc_value.Value, rErr error) {
	if s.proxy == nil {
		p, err := newProxy(pool, s.host, s.port)
		if err != nil {
			return nil, errors.Annotate(err, "call servod").Err()
		}
		s.proxy = p
	}
	newAddr := s.proxy.LocalAddr()
	host, portString, err := net.SplitHostPort(newAddr)
	if err != nil {
		return nil, errors.Annotate(err, "call servod %q", newAddr).Err()
	}
	port, err := strconv.Atoi(portString)
	if err != nil {
		return nil, errors.Annotate(err, "call servod %q", newAddr).Err()
	}
	c := xmlrpc.New(host, port)
	var iArgs []interface{}
	for _, ra := range args {
		iArgs = append(iArgs, ra)
	}
	call := xmlrpc.NewCall(method, iArgs...)
	val := &xmlrpc_value.Value{}
	err = c.Run(ctx, call, val)
	if err != nil {
		return nil, errors.Annotate(err, "call servod %q: %s", newAddr, method).Err()
	}
	return val, nil
}

// Close closes using resource.
func (s *servod) Close() error {
	if s.proxy != nil {
		if err := s.proxy.Close(); err != nil {
			return errors.Annotate(err, "close servod").Err()
		}
	}
	return nil
}
