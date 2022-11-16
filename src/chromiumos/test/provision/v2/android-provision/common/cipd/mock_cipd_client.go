// Copyright 2022 The Chromium Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"reflect"

	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/cipd/client/cipd"
)

// MockCIPDClientInterface is a mock of CIPDClient interface.
type MockCIPDClientInterface struct {
	ctrl     *gomock.Controller
	recorder *MockCIPDClientInterfaceMockRecorder
}

// MockCIPDClientInterfaceMockRecorder is the mock recorder for CIPDClient.
type MockCIPDClientInterfaceMockRecorder struct {
	mock *MockCIPDClientInterface
}

// NewMockCIPDClientInterface creates a new mock instance.
func NewMockCIPDClientInterface(ctrl *gomock.Controller) *MockCIPDClientInterface {
	mock := &MockCIPDClientInterface{ctrl: ctrl}
	mock.recorder = &MockCIPDClientInterfaceMockRecorder{mock}
	return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockCIPDClientInterface) EXPECT() *MockCIPDClientInterfaceMockRecorder {
	return m.recorder
}

// Describe mocks base method.
func (m *MockCIPDClientInterface) Describe(cipdPackageProto *api.CIPDPackage, describeTags, describeRefs bool) (*cipd.InstanceDescription, error) {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "Describe", cipdPackageProto, describeTags, describeRefs)
	ret0, _ := ret[0].(*cipd.InstanceDescription)
	ret1, _ := ret[1].(error)
	return ret0, ret1
}

// Describe indicates an expected call of Describe.
func (mr *MockCIPDClientInterfaceMockRecorder) Describe(cipdPackageProto, describeTags, describeRefs interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "Describe", reflect.TypeOf((*MockCIPDClientInterface)(nil).Describe), cipdPackageProto, describeTags, describeRefs)
}

// FetchInstanceTo mocks base method.
func (m *MockCIPDClientInterface) FetchInstanceTo(cipdPackageProto *api.CIPDPackage, packageName, instanceId, filePath string) error {
	m.ctrl.T.Helper()
	ret := m.ctrl.Call(m, "FetchInstanceTo", cipdPackageProto, packageName, instanceId, filePath)
	ret0, _ := ret[0].(error)
	return ret0
}

// FetchInstanceTo indicates an expected call of FetchInstanceTo.
func (mr *MockCIPDClientInterfaceMockRecorder) FetchInstanceTo(cipdPackageProto, packageName, instanceId, filePath interface{}) *gomock.Call {
	mr.mock.ctrl.T.Helper()
	return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "FetchInstanceTo", reflect.TypeOf((*MockCIPDClientInterface)(nil).Describe), cipdPackageProto, packageName, instanceId, filePath)
}
