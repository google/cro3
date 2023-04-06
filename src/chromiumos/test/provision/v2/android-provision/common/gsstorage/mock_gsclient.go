// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gsstorage

import (
	context "context"
	reflect "reflect"

	gomock "github.com/golang/mock/gomock"
)

// MockGsClient is a mock of GsClient interface.
type MockGsClient struct {
	ctrl     *gomock.Controller
	recorder *MockGsClientMockRecorder
}

// MockGsClientMockRecorder is the mock recorder for MockGsClient.
type MockGsClientMockRecorder struct {
	mock *MockGsClient
}

// NewMockGsClient creates a new mock instance.
func NewMockGsClient(ctrl *gomock.Controller) *MockGsClient {
	mock := &MockGsClient{ctrl: ctrl}
	mock.recorder = &MockGsClientMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockGsClient) EXPECT() *MockGsClientMockRecorder {
	return m.recorder
}

// ListFiles mocks base method.
func (m *MockGsClient) ListFiles(arg0 context.Context, arg1, arg2 string) ([]string, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "ListFiles", arg0, arg1, arg2)
	ret0, _ := ret[0].([]string)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// ListFiles indicates an expected call of ListFiles.
func (mr *MockGsClientMockRecorder) ListFiles(arg0, arg1, arg2 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ListFiles", reflect.TypeOf((*MockGsClient)(nil).ListFiles), arg0, arg1, arg2)
}

// Upload mocks base method.
func (m *MockGsClient) Upload(arg0 context.Context, arg1, arg2 string) error {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "Upload", arg0, arg1, arg2)
	ret0, _ := ret[0].(error)
	return ret0
}

// Upload indicates an expected call of Upload.
func (mr *MockGsClientMockRecorder) Upload(arg0, arg1, arg2 interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "Upload", reflect.TypeOf((*MockGsClient)(nil).Upload), arg0, arg1, arg2)
}
