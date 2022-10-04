// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package ssh helps manage a pool of SSH clients.
// This file was copy-pasted from go/src/infra/libs of chromium repo to make
// cros-servod build. Let's call this "vendoring a pinned version of sshpool".
package ssh

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"golang.org/x/crypto/ssh"
)

// Pool is a pool of SSH clients to reuse.
//
// Clients are pooled by the hostname they are connected to.
//
// Users should call Get, which returns a Client from the pool if available,
// or creates and returns a new Client.
// The returned Client is not guaranteed to be good,
// e.g., the connection may have broken while the Client was in the pool.
//
// The user should put the SSH client back into the pool after use.
// The user should not close the Client as Pool will close it if bad.
//
// The user should Close the pool after use, to free any SSH Clients in the pool.
type Pool struct {
	mu     sync.Mutex
	pool   map[string][]*ssh.Client
	config *ssh.ClientConfig
	wg     sync.WaitGroup
}

// New returns a new Pool. The provided ssh config is used for new SSH
// connections if pool has none to reuse.
func New(c *ssh.ClientConfig) *Pool {
	return &Pool{
		pool:   make(map[string][]*ssh.Client),
		config: c,
	}
}

// Get returns a good SSH client.
func (p *Pool) Get(host string) (*ssh.Client, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	for n := len(p.pool[host]) - 1; n >= 0; n-- {
		c := p.pool[host][n]
		p.pool[host] = p.pool[host][:n]
		s, err := c.NewSession()
		if err != nil {
			// This SSH client is probably bad, so close and stop using it.
			p.closeClient(c)
			continue
		}
		s.Close()
		return c, nil
	}
	c, err := ssh.Dial("tcp", host, p.config)
	return c, err
}

// GetContext returns a good SSH client within the context timeout.
func (p *Pool) GetContext(ctx context.Context, host string) (*ssh.Client, error) {
	for {
		select {
		case <-ctx.Done():
			return nil, fmt.Errorf("sshpool GetWithTimeout: timeout when trying to connect to %s", host)
		default:
			if c, err := p.Get(host); err == nil {
				return c, err
			}
			log.Printf("sshpool GetContext: retrying connection to %s", host)
			// Add a slight delay to not hammer the host with SSH connections.
			time.Sleep(2 * time.Second)
		}
	}
}

// Put puts the client back in the pool if it is good.
// Otherwise, the Client is closed.
func (p *Pool) Put(host string, c *ssh.Client) {
	if c == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	s, err := c.NewSession()
	if err != nil {
		// This SSH client is probably bad, so close and don't put into the pool.
		p.closeClient(c)
		return
	}
	s.Close()
	p.pool[host] = append(p.pool[host], c)
}

// Close closes all SSH clients in the Pool.
func (p *Pool) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()
	for hostname, cs := range p.pool {
		for _, c := range cs {
			p.closeClient(c)
		}
		delete(p.pool, hostname)
	}
	p.wg.Wait()
	return nil
}

// closeClient closes the supplied ssh.Client.
// Safe to pass in an already closed ssh.Client.
func (p *Pool) closeClient(c *ssh.Client) {
	p.wg.Add(1)
	go func() {
		defer p.wg.Done()
		// Ignore the error returned in case the client is already closed.
		// Which could happen if the DUT was rebooted, but the ssh.Client
		// is being put back into the pool.
		_ = c.Close()
	}()
}
