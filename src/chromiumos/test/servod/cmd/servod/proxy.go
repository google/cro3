// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package servod

import (
	"fmt"
	"io"
	"net"
	"sync"

	"chromiumos/test/servod/cmd/ssh"
	"go.chromium.org/luci/common/errors"
)

// proxy holds info to perform proxy confection to servod daemon.
type proxy struct {
	host     string
	connFunc func() (net.Conn, error)
	ls       net.Listener
	mutex    sync.Mutex
	errFuncs []func(error)
	closed   bool
}

const (
	// Local address with dynamic port.
	localAddr = "127.0.0.1:0"
	// Local address template for remote host.
	remoteAddrFmt = "127.0.0.1:%d"
)

// newProxy creates a new proxy with forward from remote to local host.
// Function is using a goroutine to listen and handle each incoming connection.
// Initialization of proxy is going asynchronous after return proxy instance.
func newProxy(pool *ssh.Pool, host string, remotePort int32, errFuncs ...func(error)) (*proxy, error) {
	remoteAddr := fmt.Sprintf(remoteAddrFmt, remotePort)
	connFunc := func() (net.Conn, error) {
		conn, err := pool.Get(host)
		if err != nil {
			return nil, errors.Annotate(err, "get proxy %q: fail to get client from pool", host).Err()
		}
		defer func() { pool.Put(host, conn) }()
		// Establish connection with remote server.
		return conn.Dial("tcp", remoteAddr)
	}
	// Create listener for local port.
	local, err := net.Listen("tcp", localAddr)
	if err != nil {
		return nil, err
	}
	proxy := &proxy{
		host:     host,
		ls:       local,
		connFunc: connFunc,
		errFuncs: errFuncs,
		closed:   false,
	}
	// Start a goroutine that serves as the listener and launches
	// a new goroutine to handle each incoming connection.
	// Running by goroutine to avoid waiting connections and return proxy for usage.
	go func() {
		for {
			if proxy.closed {
				break
			}
			// Waits for and returns the next connection.
			local, err := proxy.ls.Accept()
			if err != nil {
				break
			}
			go func() {
				if err := proxy.handleConn(local); err != nil && len(proxy.errFuncs) > 0 {
					proxy.mutex.Lock()
					for _, ef := range proxy.errFuncs {
						ef(err)
					}
					proxy.mutex.Unlock()
				}
			}()
		}
	}()
	return proxy, nil
}

// Close closes listening for incoming connections of proxy.
func (p *proxy) Close() error {
	p.closed = true
	p.mutex.Lock()
	p.errFuncs = nil
	p.mutex.Unlock()
	return p.ls.Close()
}

// handleConn establishes a new connection to the destination port using connFunc
// and copies data between it and src. It closes src before returning.
func (p *proxy) handleConn(src net.Conn) error {
	if p.closed {
		return errors.Reason("handle connection: proxy closed").Err()
	}
	defer func() { src.Close() }()

	dst, err := p.connFunc()
	if err != nil {
		return err
	}
	defer func() { dst.Close() }()

	ch := make(chan error)
	go func() {
		_, err := io.Copy(src, dst)
		ch <- err
	}()
	go func() {
		_, err := io.Copy(dst, src)
		ch <- err
	}()

	var firstErr error
	for i := 0; i < 2; i++ {
		if err := <-ch; err != io.EOF && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}

// LocalAddr provides assigned local address.
// Example: 127.0.0.1:23456
func (p *proxy) LocalAddr() string {
	return p.ls.Addr().String()
}
