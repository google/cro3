// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

/*
import (
	"bytes"
	"chromiumos/test/dut/cmd/dutserver/dutssh/mock_dutssh"
	"context"
	"errors"
	"io"
	"log"
	"net"
	"strings"
	"testing"

	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/test/api"
	"golang.org/x/crypto/ssh"
	"google.golang.org/grpc"
)

// Tests if DutServiceServer can handle empty request without problem.
func TestDutServiceServer_Empty(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	mci.EXPECT().Close()

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	if _, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{}); err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}
}

// Tests that a command executes successfully
func TestDutServiceServer_CommandWorks(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("command arg1 arg2")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("success!"))
				se.Write([]byte("not failed!"))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{
		Command: "command",
		Args:    []string{"arg1", "arg2"},
		Stdin:   []byte{},
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if resp.ExitInfo.Status != 0 {
		t.Fatalf("Expecting return type to be 0, instead got: %v", resp.ExitInfo.Status)
	}

	if string(resp.Stderr) != "not failed!" {
		t.Fatalf("Expecting stderr to be \"not failed!\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "success!" {
		t.Fatalf("Expecting stderr to be \"success!\", instead got %v", string(resp.Stdout))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("Started should be set!")
	}
}

// Tests that a command executes successfully
func TestDutServiceServer_CommandOptionCombineWorks(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("command arg1 arg2")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("success!"))
				se.Write([]byte("not failed!"))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{
		Command: "command",
		Args:    []string{"arg1", "arg2"},
		Stdin:   []byte{},
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_STDOUT,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "success!not failed!" {
		t.Fatalf("Expecting stderr to be \"success!not failed!\", instead got %v", string(resp.Stdout))
	}
}

// Tests that a command does not execute successfully
func TestDutServiceServer_CommandFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("command arg1 arg2")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("not success!"))
				se.Write([]byte("failure!"))
				wm := ssh.Waitmsg{}
				return &ssh.ExitError{
					Waitmsg: wm,
				}
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{
		Command: "command",
		Args:    []string{"arg1", "arg2"},
		Stdin:   []byte{},
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "failure!" {
		t.Fatalf("Expecting stderr to be \"failure\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "not success!" {
		t.Fatalf("Expecting stdout to be \"not success\", instead got %v", string(resp.Stdout))
	}

	if !resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("Started should be set!")
	}
}

// Tests that a command does not execute
func TestDutServiceServer_PreCommandFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("command arg1 arg2")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte(""))
				se.Write([]byte(""))
				return &ssh.ExitMissingError{}
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{
		Command: "command",
		Args:    []string{"arg1", "arg2"},
		Stdin:   []byte{},
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if resp.ExitInfo.Started {
		t.Fatalf("Started should not be set!")
	}
}

// Tests that a session fails
func TestDutServiceServer_NewSessionFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(nil, errors.New("Session failed.")),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.ExecCommand(ctx, &api.ExecCommandRequest{
		Command: "command",
		Args:    []string{"arg1", "arg2"},
		Stdin:   []byte{},
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	resp := &api.ExecCommandResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

	if string(resp.Stderr) != "" {
		t.Fatalf("Expecting stderr to be empty, instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "" {
		t.Fatalf("Expecting stdout to be empty, instead got %v", string(resp.Stdout))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("Signalled should not be set!")
	}

	if resp.ExitInfo.Started {
		t.Fatalf("Started should not be set!")
	}

	if resp.ExitInfo.ErrorMessage != "Session failed." {
		t.Fatalf("Error message should be session failed, instead got %v", resp.ExitInfo.ErrorMessage)
	}
}

// Tests that a path exist command fails
func TestDutServiceServer_FetchCrasesPathExistsFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().Output(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).Return(nil, errors.New("command failed!")),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: command failed!" {
		t.Fatalf("Command failure should have caused an error: %v", err)
	}

}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesPathExistsMissing(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().Output(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).Return([]byte("0"), nil),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = NotFound desc = crash_serializer not present on device." {
		t.Fatalf("Path missing should have caused an error: %v", err)
	}

}

// Tests that a new session failure fails
func TestDutServiceServer_FetchCrasesNewSessionFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(nil, errors.New("Session failed.")),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: Session failed." {
		t.Fatalf("Session Failure should have failed: %v", err)
	}

}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesSessionStartFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().Output(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).Return([]byte("1"), nil),
		msi.EXPECT().Close(),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().StdoutPipe().Return(strings.NewReader("stdout"), nil),
		msi.EXPECT().StderrPipe().Return(strings.NewReader("stderr"), nil),
		msi.EXPECT().Start(gomock.Eq("serializer_path --chunk_size=0 --fetch_coredumps")).Return(errors.New("Session Start Failure.")),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{
		FetchCore: true,
	})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to run serializer: Session Start Failure." {
		t.Fatalf("Session Start Failure should have caused an error: %v", err)
	}

}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesPipeFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().Output(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).Return([]byte("1"), nil),
		msi.EXPECT().Close(),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().StdoutPipe().Return(strings.NewReader("stdout"), errors.New("stdout failure.")),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	stream, err := cl.FetchCrashes(ctx, &api.FetchCrashesRequest{})
	if err != nil {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}

	resp := &api.FetchCrashesResponse{}
	err = stream.RecvMsg(resp)
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to get stdout: stdout failure." {
		t.Fatalf("Standard Out Failure should have caused an error: %v", err)
	}

}

// TestRestart tests that a Restart command works
func TestRestart(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().Output(gomock.Eq("reboot some args")).Return([]byte("reboot output"), nil),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
	)

	mci.EXPECT().Wait().Return(nil)

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress")
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to start DutServiceServer: %v", err)
	}
	go srv.Serve(l)
	defer srv.Stop()

	conn, err := grpc.Dial(l.Addr().String(), grpc.WithInsecure())
	if err != nil {
		t.Fatalf("Failed to dial: %v", err)
	}
	defer conn.Close()

	cl := api.NewDutServiceClient(conn)
	_, err = cl.Restart(ctx, &api.RestartRequest{
		Args: []string{"some", "args"},
	})
	// technically if we get to the reconnect step, we did everything right, so
	// rather than mock the reconnect step, we assume that if we got there, we are
	// successful
	if err.Error() != "rpc error: code = Unavailable desc = connection error: desc = \"transport: Error while dialing dial tcp: address wiringaddress: missing port in address\"" {
		t.Fatalf("Failed at api.FetchCrashes: %v", err)
	}
}
*/
