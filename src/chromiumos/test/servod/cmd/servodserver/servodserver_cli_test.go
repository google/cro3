package servodserver

import (
	"bytes"
	"chromiumos/test/servod/cmd/mock_commandexecutor"
	"chromiumos/test/servod/cmd/model"
	"context"
	"io"
	"log"
	"testing"

	"github.com/golang/mock/gomock"
)

// Tests that servod starts successfully.
func TestServodCLI_StartServodSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "start servod PORT=0 BOARD=board MODEL=model SERIAL=serialname"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		Model:         "model",
		SerialName:    "serialname",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that servod starts successfully with all input parameters.
func TestServodCLI_StartServodAllParams(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "start servod PORT=0 BOARD=board MODEL=model SERIAL=serialname DUAL_V4=allowDualV4 CONFIG=config DEBUG=debug REC_MODE=recoveryMode"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		Model:         "model",
		SerialName:    "serialname",
		AllowDualV4:   "allowDualV4",
		Config:        "config",
		Debug:         "debug",
		RecoveryMode:  "recoveryMode",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod starts successfully.
func TestServodCLI_StartServodDockerizedSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker run -d --network host --name servodDockerContainerName --env PORT=0 --env BOARD=board --env MODEL=model --env SERIAL=serialname --cap-add=NET_ADMIN --volume=/dev:/dev --privileged servodDockerImagePath /start_servod.sh"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerImagePath:     "servodDockerImagePath",
		ServodDockerContainerName: "servodDockerContainerName",
		ServodPort:                0,
		Board:                     "board",
		Model:                     "model",
		SerialName:                "serialname",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod start requires ServodDockerContainerName as input parameter.
func TestServodCLI_StartServodDockerizedWithoutContainerName(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	a := model.CliArgs{
		ServoHostPath:         "servoHostPath",
		ServodDockerImagePath: "servodDockerImagePath",
		ServodPort:            0,
		Board:                 "board",
		Model:                 "model",
		SerialName:            "serialname",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "ServodDockerContainerName not specified" {
		t.Fatalf("Expecting error reason to be \"ServodDockerContainerName not specified\", instead got %v", err.Error())
	}

	if bErr.String() != "" {
		t.Fatalf("Expecting bErr to be \"\", instead got %v", bErr.String())
	}

	if bOut.String() != "" {
		t.Fatalf("Expecting bOut to be \"\", instead got %v", bOut.String())
	}
}

// Tests that servod start requires Board as input parameter.
func TestServodCLI_StartServodWithoutBoard(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Model:         "model",
		SerialName:    "serialname",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "Board not specified" {
		t.Fatalf("Expecting error reason to be \"Board not specified\", instead got %v", err.Error())
	}

	if bErr.String() != "" {
		t.Fatalf("Expecting bErr to be \"\", instead got %v", bErr.String())
	}

	if bOut.String() != "" {
		t.Fatalf("Expecting bOut to be \"\", instead got %v", bOut.String())
	}
}

// Tests that servod start requires Model as input parameter.
func TestServodCLI_StartServodWithoutModel(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		SerialName:    "serialname",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "Model not specified" {
		t.Fatalf("Expecting error reason to be \"Model not specified\", instead got %v", err.Error())
	}

	if bErr.String() != "" {
		t.Fatalf("Expecting bErr to be \"\", instead got %v", bErr.String())
	}

	if bOut.String() != "" {
		t.Fatalf("Expecting bOut to be \"\", instead got %v", bOut.String())
	}
}

// Tests that servod start requires SerialName as input parameter.
func TestServodCLI_StartServodWithoutSerialName(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	ctx := context.Background()
	var logBuf bytes.Buffer
	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
	defer destructor()
	if err != nil {
		t.Fatalf("Failed to create new ServodService: %v", err)
	}

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Board:         "board",
		Model:         "model",
	}

	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
	if err == nil {
		t.Fatalf("Should have failed at api.ExecCmd.")
	}

	if err.Error() != "SerialName not specified" {
		t.Fatalf("Expecting error reason to be \"SerialName not specified\", instead got %v", err.Error())
	}

	if bErr.String() != "" {
		t.Fatalf("Expecting bErr to be \"\", instead got %v", bErr.String())
	}

	if bOut.String() != "" {
		t.Fatalf("Expecting bOut to be \"\", instead got %v", bOut.String())
	}
}

// Tests that servod stops successfully.
func TestServodCLI_StopServodSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "stop servod PORT=0"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
	}

	bOut, bErr, err := srv.RunCli(model.CliStopServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod stops successfully.
func TestServodCLI_StopServodDockerizedSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker exec -d servodDockerContainerName /stop_servod.sh && docker stop servodDockerContainerName"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerContainerName: "servodDockerContainerName",
		ServodPort:                0,
	}

	bOut, bErr, err := srv.RunCli(model.CliStopServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that servod command executes successfully.
func TestServodCLI_ExecCmdSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "command"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		Command:       "command",
	}

	bOut, bErr, err := srv.RunCli(model.CliExecCmd, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod command executes successfully.
func TestServodCLI_ExecCmdDockerizedSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker exec -d servodDockerContainerName 'command'"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerContainerName: "servodDockerContainerName",
		Command:                   "command",
	}

	bOut, bErr, err := srv.RunCli(model.CliExecCmd, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that servod call for DOC completes successfully.
func TestServodCLI_CallServodDocSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "dut-control -p 0 -i args"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Method:        "DOC",
		Args:          "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod call for DOC completes successfully.
func TestServodCLI_CallServodDockerizedDocSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker exec -d servodDockerContainerName 'dut-control -p 0 -i args'"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerContainerName: "servodDockerContainerName",
		ServodPort:                0,
		Method:                    "DOC",
		Args:                      "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that servod call for GET completes successfully.
func TestServodCLI_CallServodGetSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "dut-control -p 0 args"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Method:        "GET",
		Args:          "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod call for GET completes successfully.
func TestServodCLI_CallServodDockerizedGetSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker exec -d servodDockerContainerName 'dut-control -p 0 args'"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerContainerName: "servodDockerContainerName",
		ServodPort:                0,
		Method:                    "GET",
		Args:                      "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that servod call for SET completes successfully.
func TestServodCLI_CallServodSetSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "dut-control -p 0 args"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath: "servoHostPath",
		ServodPort:    0,
		Method:        "SET",
		Args:          "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// Tests that Dockerized servod call for SET completes successfully.
func TestServodCLI_CallServodDockerizedSetSuccess(t *testing.T) {
	ctrl := gomock.NewController(t)
	defer ctrl.Finish()

	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

	expectedCmd := "docker exec -d servodDockerContainerName 'dut-control -p 0 args'"

	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Eq(expectedCmd), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
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

	a := model.CliArgs{
		ServoHostPath:             "servoHostPath",
		ServodDockerContainerName: "servodDockerContainerName",
		ServodPort:                0,
		Method:                    "SET",
		Args:                      "args",
	}

	bOut, bErr, err := srv.RunCli(model.CliCallServod, a, nil, false)
	if err != nil {
		t.Fatalf("Failed at api.RunCli: %v", err)
	}

	if bErr.String() != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", bErr.String())
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}
