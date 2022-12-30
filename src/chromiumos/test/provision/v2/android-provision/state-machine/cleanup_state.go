package state_machine

import (
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"

	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type CleanupState struct {
	svc *service.AndroidService
}

func (s CleanupState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidCleanupState")
	cmds := []common_utils.CommandInterface{
		commands.NewCleanupCommand(ctx, s.svc),
	}
	for _, c := range cmds {
		// Ignore errors. Don't fail provisioning due to cleanup errors.
		c.Execute(log)
	}
	log.Println("State: AndroidCleanupState Completed")
	// Return metadata with a list of the provisioned packages.
	resp, _ := s.svc.MarshalResponseMetadata()
	return resp, api.InstallResponse_STATUS_OK, nil
}

func (s CleanupState) Next() common_utils.ServiceState {
	return nil
}

func (s CleanupState) Name() string {
	return "Android Cleanup State"
}
