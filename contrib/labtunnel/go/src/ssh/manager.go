// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"context"
	"fmt"
	"sort"
	"time"

	"chromiumos/platform/dev/contrib/labtunnel/log"
)

type Executor func(ctx context.Context, r *Runner) error

type executorState int

const (
	running executorState = iota
	waitingForRetry
	failed
	closed
)

func (s executorState) String() string {
	switch s {
	case running:
		return "RUNNING"
	case waitingForRetry:
		return "WAITING FOR RETRY"
	case failed:
		return "FAILED"
	case closed:
		return "CLOSED"
	default:
		return fmt.Sprintf("%d", s)
	}
}

type executorMessage struct {
	ctx         context.Context
	description string
	exec        Executor
	err         error
	retry       bool
}

type ConcurrentSshManager struct {
	sshRunner             *Runner
	executorChannel       chan executorMessage
	sshExecutorCount      int
	executorCtxCancellers context.CancelFunc
	retryDelay            time.Duration
	executorStates        map[string]executorState
}

func NewConcurrentSshManager(sshRunner *Runner, retryDelay time.Duration) *ConcurrentSshManager {
	return &ConcurrentSshManager{
		sshRunner:        sshRunner,
		executorChannel:  make(chan executorMessage, 100),
		sshExecutorCount: 0,
		retryDelay:       retryDelay,
		executorStates:   map[string]executorState{},
	}
}

func (m *ConcurrentSshManager) Ssh(ctx context.Context, retryOnError bool, description string, exec Executor) {
	m.sshExecutorCount++
	m.executorStates[description] = running
	log.Logger.Printf("starting ssh exec %q\n", description)
	go func() {
		err := exec(ctx, m.sshRunner)
		m.executorChannel <- executorMessage{
			ctx:         ctx,
			exec:        exec,
			description: description,
			err:         err,
			retry:       retryOnError && ctx.Err() == nil,
		}
	}()
}

func (m *ConcurrentSshManager) WaitUntilAllSshCompleted(ctx context.Context) {
executorLoop:
	for m.sshExecutorCount > 0 {
		if ctx.Err() == nil {
			m.LogExecutorStates()
		}
		select {
		case <-ctx.Done():
			for desc := range m.executorStates {
				m.executorStates[desc] = closed
			}
			break executorLoop
		case msg := <-m.executorChannel:
			m.sshExecutorCount--
			if msg.err != nil {
				m.executorStates[msg.description] = failed
				log.Logger.Printf("ssh exec %q failed, err: %v\n", msg.description, msg.err)
				if msg.retry {
					m.executorStates[msg.description] = waitingForRetry
					log.Logger.Printf("waiting %s before retrying ssh exec %q\n", m.retryDelay.String(), msg.description)
					m.LogExecutorStates()
					select {
					case <-ctx.Done():
					case <-time.After(m.retryDelay):
						m.Ssh(msg.ctx, msg.retry, msg.description, msg.exec)
					}
				}
			} else {
				delete(m.executorStates, msg.description)
				log.Logger.Printf("ssh exec %q completed successfully\n", msg.description)
			}
		}
	}
	m.LogExecutorStates()
}

func (m *ConcurrentSshManager) LogExecutorStates() {
	descriptions := make([]string, len(m.executorStates))
	i := 0
	for description := range m.executorStates {
		descriptions[i] = description
		i++
	}
	sort.Strings(descriptions)
	summary := ""
	for _, description := range descriptions {
		state := m.executorStates[description]
		summary += fmt.Sprintf("  %s  %s\n", description, state.String())
	}
	if summary == "" {
		summary = "No active ssh connections"
	}
	log.Logger.Printf("ssh state summary:\n%s", summary)
}
