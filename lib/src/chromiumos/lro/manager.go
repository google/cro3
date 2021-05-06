// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package lro provides a universal implementation of longrunning.OperationsServer,
// and helper functions for dealing with long-running operations.
package lro

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/empty"
	"github.com/google/uuid"
	"go.chromium.org/chromiumos/config/go/api/test/tls/dependencies/longrunning"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// operation is used by Manager to hold extra metadata.
type operation struct {
	op         *longrunning.Operation
	finishTime time.Time
	done       chan struct{}
}

// Manager keeps track of longrunning operations and serves operations related requests.
// Manager implements longrunning.OperationsServer.
// Manager is safe to use concurrently.
// Finished operations are expired after 30 days.
type Manager struct {
	mu sync.Mutex
	// Provide stubs for unimplemented methods
	longrunning.UnimplementedOperationsServer
	// Mapping of operation name to operation.
	operations map[string]*operation
	// expiryStopper signals the expiration goroutine to terminate.
	expiryStopper chan struct{}
}

// New returns a new Manager which must be closed after use.
func New() *Manager {
	m := &Manager{
		operations:    make(map[string]*operation),
		expiryStopper: make(chan struct{}),
	}
	go func() {
		for {
			select {
			case <-m.expiryStopper:
				return
			case <-time.After(time.Hour):
				m.deleteExpiredOperations()
			}
		}
	}()
	return m
}

// Close will close the Manager.
func (m *Manager) Close() {
	close(m.expiryStopper)
}

// NewOperation returns a new longrunning.Operation managed by Manager.
// The caller should return this directly from the gRPC method without
// modifying it or inspecting it, except to read the Name field.
func (m *Manager) NewOperation() *longrunning.Operation {
	m.mu.Lock()
	defer m.mu.Unlock()
	name := "operations/" + uuid.New().String()
	if _, ok := m.operations[name]; ok {
		panic("Generated a duplicate UUID, likely due to RNG issue.")
	}
	m.operations[name] = &operation{
		op: &longrunning.Operation{
			Name: name,
		},
		done: make(chan struct{}),
	}
	return m.operations[name].op
}

func (m *Manager) delete(name string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.operations[name]; !ok {
		return fmt.Errorf("lro delete: unknown name %s", name)
	}
	if !m.operations[name].op.Done {
		close(m.operations[name].done)
	}
	delete(m.operations, name)
	return nil
}

func (m *Manager) deleteExpiredOperations() {
	m.mu.Lock()
	defer m.mu.Unlock()
	for name, operation := range m.operations {
		// Don't do anything for an Operation which isn't done.
		if !operation.op.Done {
			continue
		}
		// If finish time is nil, panic as it should have been set when done.
		if operation.finishTime.IsZero() {
			panic(fmt.Sprintf("Missing finishTime for %s", name))
		}
		// Remove the Operation after 30 days of being done.
		expire := operation.finishTime.Add(30 * 24 * time.Hour)
		if time.Now().After(expire) {
			log.Printf("lro deleteExpiredOperations: deleting expired %s", name)
			delete(m.operations, name)
		}
	}
}

// SetResult sets the operation with the given name to done with Operation response.
// After calling this method, the caller must not mutate or read the passed-in argument
// as the manager must ensure safe concurrent access.
func (m *Manager) SetResult(name string, resp proto.Message) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.operations[name]; !ok {
		return fmt.Errorf("lro SetResult: unknown name %s", name)
	}
	if m.operations[name].op.Done {
		return fmt.Errorf("lro SetResult: name %s is already done", name)
	}
	a, err := ptypes.MarshalAny(resp)
	if err != nil {
		return err
	}
	m.operations[name].op.Result = &longrunning.Operation_Response{
		Response: a,
	}
	m.operations[name].finishTime = time.Now()
	m.operations[name].op.Done = true
	close(m.operations[name].done)
	return nil
}

// SetError sets the operation with the given name to done with Operation error.
// After calling this method, the caller must not mutate or read the passed-in argument
// as the manager must ensure safe concurrent access.
func (m *Manager) SetError(name string, opErr *status.Status) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.operations[name]; !ok {
		return fmt.Errorf("lro SetError: unknown name %s", name)
	}
	if m.operations[name].op.Done {
		return fmt.Errorf("lro SetError: name %s is already done", name)
	}
	s := opErr.Proto()
	m.operations[name].op.Result = &longrunning.Operation_Error{
		Error: &longrunning.Status{
			Code:    s.GetCode(),
			Message: s.GetMessage(),
			Details: s.GetDetails(),
		},
	}
	m.operations[name].finishTime = time.Now()
	m.operations[name].op.Done = true
	close(m.operations[name].done)
	return nil
}

func (m *Manager) getOperationClone(name string) (*longrunning.Operation, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	v, ok := m.operations[name]
	if !ok {
		return nil, status.Errorf(codes.NotFound, "name %s does not exist", name)
	}
	return proto.Clone(v.op).(*longrunning.Operation), nil
}

// GetOperation returns the longrunning.Operation if managed.
func (m *Manager) GetOperation(ctx context.Context, req *longrunning.GetOperationRequest) (*longrunning.Operation, error) {
	return m.getOperationClone(req.Name)
}

// DeleteOperation deletes the longrunning.Operation if managed.
func (m *Manager) DeleteOperation(ctx context.Context, req *longrunning.DeleteOperationRequest) (*empty.Empty, error) {
	name := req.Name
	if err := m.delete(name); err != nil {
		return nil, status.Error(codes.NotFound, fmt.Sprintf("failed to delete name %s, %s", name, err))
	}
	return &empty.Empty{}, nil
}

func (m *Manager) getOperationChannel(name string) (chan struct{}, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	v, ok := m.operations[name]
	if !ok {
		return nil, ok
	}
	return v.done, ok
}

// WaitOperation returns once the longrunning.Operation is done or timeout.
func (m *Manager) WaitOperation(ctx context.Context, req *longrunning.WaitOperationRequest) (*longrunning.Operation, error) {
	name := req.Name
	ch, ok := m.getOperationChannel(name)
	if !ok {
		return nil, status.Error(codes.NotFound, fmt.Sprintf("name %s does not exist", name))
	}

	if req.Timeout != nil && req.Timeout.Seconds > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, req.Timeout.AsDuration())
		defer cancel()
	}

	// Wait until the operation is done or timeout.
	select {
	case <-ch:
	case <-ctx.Done():
	}
	return m.getOperationClone(name)
}
