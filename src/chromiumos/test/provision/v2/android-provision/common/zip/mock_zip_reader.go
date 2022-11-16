// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package zip

import (
	"reflect"

	"github.com/golang/mock/gomock"
)

// MockZipReaderInterface is a mock of ZipReader interface.
type MockZipReaderInterface struct {
	ctrl     *gomock.Controller
	recorder *MockZipReaderInterfaceMockRecorder
}

// MockZipReaderInterfaceMockRecorder is the mock recorder for ZipReader.
type MockZipReaderInterfaceMockRecorder struct {
	mock *MockZipReaderInterface
}

// NewMockZipReaderInterface creates a new mock instance.
func NewMockZipReaderInterface(ctrl *gomock.Controller) *MockZipReaderInterface {
	mock := &MockZipReaderInterface{ctrl: ctrl}
	mock.recorder = &MockZipReaderInterfaceMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockZipReaderInterface) EXPECT() *MockZipReaderInterfaceMockRecorder {
	return m.recorder
}

// UnzipFile mocks base method.
func (m *MockZipReaderInterface) UnzipFile(srcFile, dstPath string) error {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "UnzipFile", srcFile, dstPath)
	ret0, _ := ret[0].(error)
	return ret0
}

// UnzipFile indicates an expected call of UnzipFile.
func (mr *MockZipReaderInterfaceMockRecorder) UnzipFile(srcFile, dstPath interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "UnzipFile", reflect.TypeOf((*MockZipReaderInterface)(nil).UnzipFile), srcFile, dstPath)
}
