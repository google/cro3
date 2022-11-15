package state_machine

import (
	"context"
	"fmt"
	"log"

	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type CleanupState struct {
	svc *service.AndroidService
}

func (s CleanupState) Execute(ctx context.Context, log *log.Logger) error {
	log.Printf("%s: begin Execute", s.Name())
	cmds := []common_utils.CommandInterface{
		commands.NewCleanupCommand(ctx, s.svc),
	}
	for _, c := range cmds {
		if err := c.Execute(log); err != nil {
			return fmt.Errorf("%s: %s", c.GetErrorMessage(), err)
		}
	}
	return nil
}

func (s CleanupState) Next() common_utils.ServiceState {
	return nil
}

func (s CleanupState) Name() string {
	return "Android Cleanup State"
}
