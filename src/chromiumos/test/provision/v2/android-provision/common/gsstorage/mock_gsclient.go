// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package gsstorage

import (
	context "context"
	reflect "reflect"

	gomock "github.com/golang/mock/gomock"
)

// MockgsClient is a mock of gsClient interface.
type MockgsClient struct {
	ctrl     *gomock.Controller
	recorder *MockgsClientMockRecorder
}

// MockgsClientMockRecorder is the mock recorder for MockgsClient.
type MockgsClientMockRecorder struct {
	mock *MockgsClient
}

// NewMockgsClient creates a new mock instance.
func NewMockgsClient(ctrl *gomock.Controller) *MockgsClient {
	mock := &MockgsClient{ctrl: ctrl}
	mock.recorder = &MockgsClientMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockgsClient) EXPECT() *MockgsClientMockRecorder {
	return m.recorder
}

// Upload mocks base method.
func (m *MockgsClient) Upload(ctx context.Context, apkLocalPath, apkName string) error {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "Upload", ctx, apkLocalPath, apkName)
	ret1, _ := ret[0].(error)
	return ret1
}

// Upload indicates an expected call of Upload.
func (mr *MockgsClientMockRecorder) Upload(ctx, apkLocalPath, apkName interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "Upload", reflect.TypeOf((*MockgsClient)(nil).Upload), ctx, apkLocalPath, apkName)
}
