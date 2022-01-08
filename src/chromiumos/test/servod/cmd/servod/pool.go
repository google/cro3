// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package servod

import (
	"fmt"

	"go.chromium.org/luci/common/errors"
)

// Pool is a pool of servod to reuse.
//
// Servo are pooled by the `address:port|remote`  they are connected to.
//
// Users should call Get, which returns a instance from the pool if available,
// or creates and returns a new one.
// The returned servod is not guaranteed to be good,
// e.g., the connection may have broken while the Client was in the pool.
//
// The user should not close the servod as Pool will close it at the end.
//
// The user should Close the pool after use, to free any resources in the pool.
type Pool struct {
	servos map[string]*servod
}

// NewPool returns a new Pool. The provided ssh config is used for new SSH
// connections if pool has none to reuse.
func NewPool() *Pool {
	return &Pool{
		servos: make(map[string]*servod),
	}
}

// Close closes all active servodes.
func (p *Pool) Close() error {
	for k, s := range p.servos {
		if err := s.Close(); err != nil {
			return errors.Annotate(err, "close pool").Err()
		}
		delete(p.servos, k)
	}
	return nil
}

// getServoParams function to receive start params for servod.
type getServoParams func() ([]string, error)

// Get provides servod from cache or initiate new one.
func (p *Pool) Get(servoAddr string, servodPort int32, getParams getServoParams) (*servod, error) {
	if s, ok := p.servos[createKey(servoAddr, servodPort)]; ok {
		return s, nil
	}
	s, err := p.init(servoAddr, servodPort, getParams)
	if err != nil {
		return nil, errors.Annotate(err, "get from pool").Err()
	}
	return s, nil
}

// init creates new servod instance and places it in the cache.
func (p *Pool) init(servoAddr string, servodPort int32, getParams getServoParams) (*servod, error) {
	if getParams == nil {
		return nil, errors.Reason("init servod: getParams is not provided").Err()
	}
	if servoAddr == "" {
		return nil, errors.Reason("init servod: servoAddr is empty").Err()
	}
	if servodPort > 9999 || servodPort < 1 {
		return nil, errors.Reason("init servod: servodPort expected to in range 1-9999").Err()
	}
	s := &servod{
		host:      servoAddr,
		port:      servodPort,
		getParams: getParams,
	}
	p.servos[createKey(servoAddr, servodPort)] = s
	return s, nil
}

// createKey creates key for the pool.
func createKey(servoAddr string, servodPort int32) string {
	return fmt.Sprintf("%s|%d", servoAddr, servodPort)
}
