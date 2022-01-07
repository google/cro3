// Code generated by MockGen. DO NOT EDIT.
// Source: /usr/local/google/home/denizkara/chromeos/src/platform/dev/src/chromiumos/test/servod/cmd/commandexecutor/commandexecutor.go

// Package mock_commandexecutor is a generated GoMock package.
package mock_commandexecutor

import (
        bytes "bytes"
        io "io"
        reflect "reflect"

        gomock "github.com/golang/mock/gomock"
)

// MockCommandExecutorInterface is a mock of CommandExecutorInterface interface.
type MockCommandExecutorInterface struct {
        ctrl     *gomock.Controller
        recorder *MockCommandExecutorInterfaceMockRecorder
}

// MockCommandExecutorInterfaceMockRecorder is the mock recorder for MockCommandExecutorInterface.
type MockCommandExecutorInterfaceMockRecorder struct {
        mock *MockCommandExecutorInterface
}

// NewMockCommandExecutorInterface creates a new mock instance.
func NewMockCommandExecutorInterface(ctrl *gomock.Controller) *MockCommandExecutorInterface {
        mock := &MockCommandExecutorInterface{ctrl: ctrl}
        mock.recorder = &MockCommandExecutorInterfaceMockRecorder{mock}
        return mock
}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *MockCommandExecutorInterface) EXPECT() *MockCommandExecutorInterfaceMockRecorder {
        return m.recorder
}

// Run mocks base method.
func (m *MockCommandExecutorInterface) Run(addr, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
        m.ctrl.T.Helper()
        ret := m.ctrl.Call(m, "Run", addr, command, stdin, routeToStd)
        ret0, _ := ret[0].(bytes.Buffer)
        ret1, _ := ret[1].(bytes.Buffer)
        ret2, _ := ret[2].(error)
        return ret0, ret1, ret2
}

// Run indicates an expected call of Run.
func (mr *MockCommandExecutorInterfaceMockRecorder) Run(addr, command, stdin, routeToStd interface{}) *gomock.Call {
        mr.mock.ctrl.T.Helper()
        return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "Run", reflect.TypeOf((*MockCommandExecutorInterface)(nil).Run), addr, command, stdin, routeToStd)
}