// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"chromiumos/test/dut/cmd/cros-dut/dutssh/mock_dutssh"
	"context"
	"errors"
	"fmt"
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

// Tests that a command executes successfully
func TestDutServiceServer_CommandWorks(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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
		mci.EXPECT().IsAlive().Return(true),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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
		mci.EXPECT().IsAlive().Return(true),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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
		mci.EXPECT().IsAlive().Return(true),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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

// Tests that IsAliveFailure leads to a reconnect
func TestDutServiceServer_IsAliveFailureInCommandReconnects(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)

	mci.EXPECT().IsAlive().Return(false)
	mci.EXPECT().Close()

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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

	// technically if we get to the reconnect step, we did everything right, so
	// rather than mock the reconnect step, we assume that if we got there, we are
	// successful
	if resp.ExitInfo == nil {
		t.Fatalf("Exit info should be populated")
	}
	if !strings.Contains(resp.ExitInfo.ErrorMessage, "connection error") {
		t.Fatalf("Failed at api.ExecCommand: %v", err)
	}

}

// Tests that a session fails
func TestDutServiceServer_NewSessionFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(nil, errors.New("Session failed.")),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "", 0, "dutname", "wiringaddress", "cacheaddress")
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

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("not success!"))
				se.Write([]byte("failed!"))
				return errors.New("command failed!")
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: failed!" {
		t.Fatalf("Command failure should have caused an error: %v", err)
	}

}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesPathExistsMissing(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("0"))
				se.Write([]byte(""))
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(nil, errors.New("Session failed.")),
		mci.EXPECT().Close(),
	)
	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	if err.Error() != "rpc error: code = FailedPrecondition desc = Failed to check crash_serializer existence: " {
		t.Fatalf("Session Failure should have failed: %v", err)
	}

}

// Tests that a path exist command returns command missing
func TestDutServiceServer_FetchCrasesSessionStartFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("1"))
				se.Write([]byte(""))
				return nil
			},
		),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("[ -e serializer_path ] && echo -n 1 || echo -n 0")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("1"))
				se.Write([]byte(""))
				return nil
			},
		),
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("cat /proc/sys/kernel/random/boot_id")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("123"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),

		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("reboot some args")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("reboot output"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().Close(),
		// TODO b/253462116: fix this unittest to be more correct
		// This should have a set of calls for checking the boot_id again, but for some reason,
		// it doesn't work. When they are added, the mock complains about this.
	)
	mci.EXPECT().Wait().Return(nil)

	var logBuf bytes.Buffer
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		t.Fatal("Failed to create a net listener: ", err)
	}

	ctx := context.Background()
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
		Retry: &api.RestartRequest_ReconnectRetry{
			Times:      1,
			IntervalMs: 100,
		},
	})
	// technically if we get to the reconnect step, we did everything right, so
	// rather than mock the reconnect step, we assume that if we got there, we are
	// successful
	if !strings.Contains(err.Error(), "connection error") {
		t.Fatalf("Failed at api.Restart: %v", err)
	}
}

// TestCache tests that the regular Cache command works
func TestCache(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("mkdir -p /dest")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("worked"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/download/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("curl output"))
				se.Write([]byte(""))
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: "gs://source/path"},
		},
	})

	if err != nil {
		t.Fatalf("Failed at api.Cache: %v", err)
	}
}

// We need to make sure that on error all retries are triggered up to failure
func TestCachePipeRetriesAllTimes(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("mkdir -p /dest")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("worked"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/download/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("failed!"))
				se.Write([]byte("failed!"))
				return fmt.Errorf("Failed curl!")
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/download/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("failed!"))
				se.Write([]byte("failed!"))
				return fmt.Errorf("Failed curl!")
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/download/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("failed!"))
				se.Write([]byte("failed!"))
				return fmt.Errorf("Failed curl!")
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: "gs://source/path"},
		},
		Retry: &api.CacheRequest_Retry{
			Times:      2,
			IntervalMs: 100,
		},
	})

	if err == nil {
		t.Fatalf("Expected failure")
	}

}

// TestCachePipe tests that the regular Cache command works and pipes the file
func TestCachePipe(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 cacheaddress/download/source/path | piped commands")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("curl output"))
				se.Write([]byte(""))
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_Pipe_{
			Pipe: &api.CacheRequest_Pipe{
				Commands: "piped commands",
			},
		},
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: "gs://source/path"},
		},
	})

	if err != nil {
		t.Fatalf("Failed at api.Cache: %v", err)
	}

}

// TestUntarCache tests that the untar Cache command works
func TestUntarCache(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("mkdir -p /dest")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("worked"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/extract/source/path?file=somefile")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("curl output"))
				se.Write([]byte(""))
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsTarFile{
			GsTarFile: &api.CacheRequest_GSTARFile{
				SourcePath: "gs://source/path",
				SourceFile: "somefile",
			},
		},
	})

	if err != nil {
		t.Fatalf("Failed at api.Cache: %v", err)
	}

}

// TestUnzipCache tests that the unzip Cache command works
func TestUnzipCache(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("mkdir -p /dest")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("worked"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/decompress/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("curl output"))
				se.Write([]byte(""))
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsZipFile{
			GsZipFile: &api.CacheRequest_GSZipFile{
				SourcePath: "gs://source/path",
			},
		},
	})

	if err != nil {
		t.Fatalf("Failed at api.Cache: %v", err)
	}

}

// TestCacheFailsWrongURL tests that the unzip Cache fails on a URL which doesn't comply
func TestCacheFailsWrongURL(t *testing.T) {
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsZipFile{
			GsZipFile: &api.CacheRequest_GSZipFile{
				SourcePath: "source/path",
			},
		},
	})

	if err == nil {
		t.Fatalf("Expected failure due to improper formatting")
	}

}

// TestCacheFailsCommandFails tests that the unzip Cache fails on a URL which doesn't comply
func TestCacheFailsCommandFails(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mci := mock_dutssh.NewMockClientInterface(ctrl)
	msi := mock_dutssh.NewMockSessionInterface(ctrl)

	var so io.Writer
	var se io.Writer

	gomock.InOrder(
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("mkdir -p /dest")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte("worked"))
				se.Write([]byte(""))
				return nil
			},
		),
		msi.EXPECT().Close(),
		mci.EXPECT().IsAlive().Return(true),
		mci.EXPECT().NewSession().Return(msi, nil),
		msi.EXPECT().SetStdout(gomock.Any()).Do(func(arg io.Writer) { so = arg }),
		msi.EXPECT().SetStderr(gomock.Any()).Do(func(arg io.Writer) { se = arg }),
		msi.EXPECT().Run(gomock.Eq("curl --keepalive-time 20 -S -s -v -# -C - --retry 3 --retry-delay 60 -o /dest/path cacheaddress/download/source/path")).DoAndReturn(
			func(arg string) error {
				so.Write([]byte(""))
				se.Write([]byte("failed download"))
				return fmt.Errorf("couldn't download")
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.Cache(ctx, &api.CacheRequest{
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: "/dest/path",
			},
		},
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: "gs://source/path",
			},
		},
	})

	if !strings.Contains(err.Error(), "couldn't download") {
		t.Fatalf("Failed at api.Cache: %v", err)
	}

}

// TestForceReconnect tests that a Restart command works
func TestForceReconnect(t *testing.T) {
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
	srv, destructor := newDutServiceServer(l, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mci, "serializer_path", 0, "dutname", "wiringaddress", "cacheaddress")
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
	_, err = cl.ForceReconnect(ctx, &api.ForceReconnectRequest{})

	// technically if we get to the reconnect step, we did everything right, so
	// rather than mock the reconnect step, we assume that if we got there, we are
	// successful
	if !strings.Contains(err.Error(), "connection error") {
		t.Fatalf("Failed at api.Restart: %v", err)
	}
}
