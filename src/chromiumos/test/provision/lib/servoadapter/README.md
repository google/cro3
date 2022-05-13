# ServoHostAdapter

ServoHostAdapter will be deleted whenever cros-servod starts working on non-labstation devices, and replaced with RPC calls.

ServoHostAdapter is a lightweight adapter that expands `ExecCmder` interface with servod-related functionality.

Given following interface
```
ExecCmd(ctx context.Context, in *api.ExecCmdRequest, opts ...grpc.CallOption) (*api.ExecCmdResponse, error)
```

ServoHostAdapter implements the functionality of `services.ServiceAdapterInterface`,
which currently includes following functions:
```
	// RunCmd takes a command and argument and executes it remotely in the DUT,
	// returning the stdout as the string result and any execution error as the error.
	RunCmd(ctx context.Context, cmd string, args []string) (string, error)
	// Restart restarts a DUT (allowing cros-dut to reconnect for connection caching).
	Restart(ctx context.Context) error
	// PathExists is a simple wrapper for RunCmd for the sake of simplicity. If
	// the path exists True is returned, else False. An error implies a
	// a communication failure.
	PathExists(ctx context.Context, path string) (bool, error)
	// PipeData uses the caching infrastructure to bring an image into the lab.
	// Contrary to CopyData, the data here is pipeable to whatever is fed into
	// pipeCommand, rather than directly placed locally.
	PipeData(ctx context.Context, sourceUrl string, pipeCommand string) error
	// CopyData uses the caching infrastructure to copy a remote image to
	// the local path specified by destPath.
	CopyData(ctx context.Context, sourceUrl string, destPath string) error
	// DeleteDirectory is a simple wrapper for RunCmd for the sake of simplicity.
	DeleteDirectory(ctx context.Context, dir string) error
	// CreateDirectory is a simple wrapper for RunCmd for the sake of simplicity.
	// All directories specified in the array will be created.
	// As this uses "-p" option, subdirs are created regardless of whether parents
	// exist or not.
	CreateDirectories(ctx context.Context, dirs []string) error
```
and adds following additional servod-related functions:
```
	// Returns value of a variable, requested with dut-control.
	GetVariable(ctx context.Context, varName string) (string, error)
	// Runs a single dut-control command with |args| as its arguments.
	RunDutControl(ctx context.Context, args []string) error
	// Runs an array of dut-control commands.
	RunAllDutControls(ctx context.Context, cmdFragments [][]string) error

	GetBoard(ctx context.Context) string
	GetModel(ctx context.Context) string
```
