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

	if string(bErr.String()) != "not failed!" {
		t.Fatalf("Expecting bErr to be \"not failed!\", instead got %v", string(bErr.String()))
	}

	if string(bOut.String()) != "success!" {
		t.Fatalf("Expecting bOut to be \"success!\", instead got %v", string(bOut.String()))
	}
}

// // Tests that servod starts successfully.
// func TestServodCLI_StartServodInvalidInput(t *testing.T) {
// 	ctrl := gomock.NewController(t)
// 	defer ctrl.Finish()

// 	mce := mock_commandexecutor.NewMockCommandExecutorInterface(ctrl)

// 	mce.EXPECT().Run(gomock.Eq("servoHostPath"), gomock.Any(), gomock.Eq(nil), gomock.Eq(false)).DoAndReturn(
// 		func(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
// 			var bOut, bErr bytes.Buffer
// 			bOut.Write([]byte("not success!"))
// 			bErr.Write([]byte("failed!"))
// 			return bOut, bErr, nil
// 		},
// 	)

// 	ctx := context.Background()
// 	var logBuf bytes.Buffer
// 	srv, destructor, err := NewServodService(ctx, log.New(&logBuf, "", log.LstdFlags|log.LUTC), mce)
// 	defer destructor()
// 	if err != nil {
// 		t.Fatalf("Failed to create new ServodService: %v", err)
// 	}

// 	a := model.CliArgs{
// 		ServoHostPath: "servoHostPath",
// 		ServodPort:    0,
// 	}

// 	bOut, bErr, err := srv.RunCli(model.CliStartServod, a, nil, false)
// 	if err == nil {
// 		t.Fatalf("Should have failed at api.ExecCmd.")
// 	}

// 	if string(bErr.String()) != "failed!" {
// 		t.Fatalf("Expecting bErr to be \"failed!\", instead got %v", string(bErr.String()))
// 	}

// 	if string(bOut.String()) != "not success!" {
// 		t.Fatalf("Expecting bOut to be \"not success!\", instead got %v", string(bOut.String()))
// 	}
// }
