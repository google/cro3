package servodserver

import (
	"bytes"
	"chromiumos/test/servod/cmd/mock_commandexecutor"
	"context"
	"io"
	"log"
	"testing"

	"github.com/golang/mock/gomock"
	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
)

// Tests that servod starts successfully.
func TestServodServer_StartServodSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("success!"))
			bErr.Write([]byte("not failed!"))
			return bOut, bErr, nil
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	op, err := srv.StartServod(ctx, &api.StartServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		Model:         "model",
		SerialName:    "serialname",
	})
	if err != nil {
		t.Fatalf("Failed at api.StartServod: %v", err)
	}

	switch op.Result.(type) {
	case *longrunning.Operation_Error:
		t.Fatalf("Failed at api.StartServod: %v", err)
	}
}

// Tests that servod start failure is handled successfully.
func TestServodServer_StartServodFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("not success!"))
			bErr.Write([]byte("failed!"))
			return bOut, bErr, errors.Reason("error message").Err()
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	op, err := srv.StartServod(ctx, &api.StartServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		Model:         "model",
		SerialName:    "serialname",
	})
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "error message" {
		t.Fatalf("Expecting Error to be \"error message\", instead got %v", err.Error())
	}

	switch op.Result.(type) {
	case *longrunning.Operation_Error:
		t.Fatalf("Failed at api.StartServod: %v", err)
	}
}

// Tests that servod stops successfully.
func TestServodServer_StopServodSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("success!"))
			bErr.Write([]byte("not failed!"))
			return bOut, bErr, nil
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	op, err := srv.StopServod(ctx, &api.StopServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
	})
	if err != nil {
		t.Fatalf("Failed at api.StopServod: %v", err)
	}

	switch op.Result.(type) {
	case *longrunning.Operation_Error:
		t.Fatalf("Failed at api.StopServod: %v", err)
	}
}

// Tests that servod stop failure is handled successfully.
func TestServodServer_StopServodFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("not success!"))
			bErr.Write([]byte("failed!"))
			return bOut, bErr, errors.Reason("error message").Err()
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	op, err := srv.StopServod(ctx, &api.StopServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
	})
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "error message" {
		t.Fatalf("Expecting Error to be \"error message\", instead got %v", err.Error())
	}

	switch op.Result.(type) {
	case *longrunning.Operation_Error:
		t.Fatalf("Failed at api.StopServod: %v", err)
	}
}

// Tests that a command executes successfully.
func TestServodServer_ExecCmdSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq("command arg1 arg2"), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("success!"))
			bErr.Write([]byte("not failed!"))
			return bOut, bErr, nil
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	resp, err := srv.ExecCmd(ctx, &api.ExecCmdRequest{
		ServoHostPath: "servoHostPath",
		Command:       "command arg1 arg2",
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	if string(resp.Stderr) != "not failed!" {
		t.Fatalf("Expecting Stderr to be \"not failed!\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "success!" {
		t.Fatalf("Expecting Stdout to be \"success!\", instead got %v", string(resp.Stdout))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("ExitInfo.Signaled should not be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("ExitInfo.Started should be set!")
	}

	if resp.ExitInfo.Status != 0 {
		t.Fatalf("Expecting ExitInfo.Status to be 0, instead got: %v", resp.ExitInfo.Status)
	}
}

// Tests that a command with stdin executes successfully.
func TestServodServer_ExecCmdWithStdinSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	stdin := []byte("stdin")
	var expectedStdin io.Reader = bytes.NewReader(stdin)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq("command arg1 arg2"), gomock.Eq(expectedStdin), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("success!"))
			bErr.Write([]byte("not failed!"))
			return bOut, bErr, nil
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	resp, err := srv.ExecCmd(ctx, &api.ExecCmdRequest{
		ServoHostPath: "servoHostPath",
		Command:       "command arg1 arg2",
		Stdin:         stdin,
	})
	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	if string(resp.Stderr) != "not failed!" {
		t.Fatalf("Expecting Stderr to be \"not failed!\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "success!" {
		t.Fatalf("Expecting Stdout to be \"success!\", instead got %v", string(resp.Stdout))
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("ExitInfo.Signaled should not be set!")
	}

	if !resp.ExitInfo.Started {
		t.Fatalf("ExitInfo.Started should be set!")
	}

	if resp.ExitInfo.Status != 0 {
		t.Fatalf("Expecting ExitInfo.Status to be 0, instead got: %v", resp.ExitInfo.Status)
	}
}

// Tests that a command execution failure is handled gracefully.
func TestServodServer_ExecCmdFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq("command arg1 arg2"), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("not success!"))
			bErr.Write([]byte("failed!"))
			return bOut, bErr, errors.Reason("error message").Err()
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	resp, err := srv.ExecCmd(ctx, &api.ExecCmdRequest{
		ServoHostPath: "servoHostPath",
		Command:       "command arg1 arg2",
	})
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if string(resp.Stderr) != "failed!" {
		t.Fatalf("Expecting Stderr to be \"failed!\", instead got %v", string(resp.Stderr))
	}

	if string(resp.Stdout) != "not success!" {
		t.Fatalf("Expecting Stdout to be \"not success!\", instead got %v", string(resp.Stdout))
	}

	if resp.ExitInfo.ErrorMessage != "error message" {
		t.Fatalf("Expecting ExitInfo.ErrorMessage to be \"error message\", instead got %v", resp.ExitInfo.ErrorMessage)
	}

	if resp.ExitInfo.Signaled {
		t.Fatalf("ExitInfo.Signaled should not be set!")
	}

	if resp.ExitInfo.Started {
		t.Fatalf("ExitInfo.Started should not be set!")
	}

	if resp.ExitInfo.Status == 0 {
		t.Fatalf("Expecting ExitInfo.Status to be not 0, instead got: %v", resp.ExitInfo.Status)
	}
}

// Tests that calling servod is successful.
func TestServodServer_CallServodSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("success!"))
			bErr.Write([]byte("not failed!"))
			return bOut, bErr, nil
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	resp, err := srv.CallServod(ctx, &api.CallServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    9901,
		Method:        api.CallServodRequest_DOC,
		Args:          "arg1",
	})
	if err != nil {
		t.Fatalf("Failed at api.CallServod: %v", err)
	}

	if resp.GetFailure() != nil {
		t.Fatalf("Expecting GetFailure() to be nil, instead got %v", resp.GetFailure().ErrorMessage)
	}

	if resp.GetSuccess().Result != "success!" {
		t.Fatalf("Expecting GetSuccess().Result to be \"success!\", instead got %v", resp.GetSuccess().Result)
	}
}

// Tests that calling servod failure is handled gracefully.
func TestServodServer_CallServodFailure(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
			var bOut, bErr bytes.Buffer
			bOut.Write([]byte("not success!"))
			bErr.Write([]byte("failed!"))
			return bOut, bErr, errors.Reason("error message").Err()
		},
	)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	resp, err := srv.CallServod(ctx, &api.CallServodRequest{
		ServoHostPath: "servoHostPath",
		ServodPort:    9901,
		Method:        api.CallServodRequest_DOC,
		Args:          "arg1",
	})
	if err == nil {
		t.Fatalf("Should have failed at api.CallServod.")
	}

	if resp.GetFailure().ErrorMessage != "failed!" {
		t.Fatalf("Expecting GetFailure().ErrorMessage to be \"failed!\", instead got %v", resp.GetFailure().ErrorMessage)
	}

	if resp.GetSuccess() != nil {
		t.Fatalf("Expecting GetSuccess() to be nil, instead got %v", resp.GetSuccess().Result)
	}
}

/*
//NOTE: The following tests are for INTEGRATION TESTING PURPOSES and will be REMOVED before merging to master.

var (
	tls                = flag.Bool("tls", false, "Connection uses TLS if true, else plain TCP")
	caFile             = flag.String("ca_file", "", "The file containing the CA root cert file")
	serverAddr         = flag.String("addr", "localhost:8080", "The server address in the format of host:port")
	serverHostOverride = flag.String("server_host_override", "x.test.example.com", "The server name used to verify the hostname returned by the TLS handshake")
)

func TestStartServodSuccess(t *testing.T) {
	flag.Parse()
	opts := getDialOptions()

	conn, err := grpc.Dial(*serverAddr, opts...)
	if err != nil {
		log.Fatalf("fail to dial: %v", err)
	}
	defer conn.Close()
	client := api.NewServodServiceClient(conn)

	op, err := client.StartServod(context.Background(), &api.StartServodRequest{
		ServoHostPath:             "localhost:9876",
		ServodDockerContainerName: "",
		ServodDockerImagePath:     "",
		ServodPort:                9901,
		Board:                     "dedede",
		Model:                     "galith",
		SerialName:                "G1911050826",
		Debug:                     "",
		RecoveryMode:              "",
		Config:                    "",
		AllowDualV4:               "",
	})

	if op != nil {
		fmt.Println(op.Result)
	}
}

func TestStopServodSuccess(t *testing.T) {
	flag.Parse()
	opts := getDialOptions()

	conn, err := grpc.Dial(*serverAddr, opts...)
	if err != nil {
		log.Fatalf("fail to dial: %v", err)
	}
	defer conn.Close()
	client := api.NewServodServiceClient(conn)

	op, err := client.StopServod(context.Background(), &api.StopServodRequest{
		ServoHostPath:             "localhost:9876",
		ServodDockerContainerName: "",
		ServodPort:                9901,
	})

	if op != nil {
		fmt.Println(op.Result)
	}
}

func TestExecCmdRemoteSuccess(t *testing.T) {
	flag.Parse()
	opts := getDialOptions()

	conn, err := grpc.Dial(*serverAddr, opts...)
	if err != nil {
		log.Fatalf("fail to dial: %v", err)
	}
	defer conn.Close()
	client := api.NewServodServiceClient(conn)

	stream, err := client.ExecCmd(context.Background(), &api.ExecCmdRequest{
		ServoHostPath:             "localhost:9876",
		ServodDockerContainerName: "",
		Command:                   "ps -ef | grep servod",
		Stdin:                     []byte{},
	})

	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	resp := &api.ExecCmdResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	fmt.Println(resp)
}

func TestExecCmdLocalSuccess(t *testing.T) {
	flag.Parse()
	opts := getDialOptions()

	conn, err := grpc.Dial(*serverAddr, opts...)
	if err != nil {
		log.Fatalf("fail to dial: %v", err)
	}
	defer conn.Close()
	client := api.NewServodServiceClient(conn)

	stream, err := client.ExecCmd(context.Background(), &api.ExecCmdRequest{
		ServoHostPath:             "",
		ServodDockerContainerName: "",
		Command:                   "ls -ll",
		Stdin:                     []byte{},
	})

	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	resp := &api.ExecCmdResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.ExecCmd: %v", err)
	}

	fmt.Println(resp)
}

func TestCallServodSuccess(t *testing.T) {
	flag.Parse()
	opts := getDialOptions()

	conn, err := grpc.Dial(*serverAddr, opts...)
	if err != nil {
		log.Fatalf("fail to dial: %v", err)
	}
	defer conn.Close()
	client := api.NewServodServiceClient(conn)

	stream, err := client.CallServod(context.Background(), &api.CallServodRequest{
		ServoHostPath:             "localhost:9876",
		ServodDockerContainerName: "",
		ServodPort:                9901,
		Method:                    api.CallServodRequest_DOC,
		// Method: api.CallServodRequest_GET,
		// Method: api.CallServodRequest_SET,
		Args: "lid_openXYZ",
		// Args: "lid_open:yes",
	})

	if err != nil {
		t.Fatalf("Failed at api.CallServod: %v", err)
	}

	resp := &api.CallServodResponse{}
	err = stream.RecvMsg(resp)
	if err != nil {
		t.Fatalf("Failed at api.CallServod: %v", err)
	}

	fmt.Println(resp)
}

func getDialOptions() []grpc.DialOption {
	var opts []grpc.DialOption
	if *tls {
		if *caFile == "" {
			*caFile = data.Path("x509/ca_cert.pem")
		}
		creds, err := credentials.NewClientTLSFromFile(*caFile, *serverHostOverride)
		if err != nil {
			log.Fatalf("Failed to create TLS credentials %v", err)
		}
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		opts = append(opts, grpc.WithInsecure())
	}
	return opts
}
*/
