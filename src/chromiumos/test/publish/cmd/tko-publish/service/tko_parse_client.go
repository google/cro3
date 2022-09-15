package service

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
)

// Path to python binary inside the container.
const pythonPath = "/usr/local/bin/python3"

// Path to tko parse script inside the container.
const tkoParsePath = "/usr/local/autotest/tko/parse.py"

// TkoParseRequest holds information needed by tko/parse CLI.
type TkoParseRequest struct {
	// Path to test results to upload
	ResultsDir string
	// Job name to be passed to tko-parse
	JobName string
}

// tkoParseCmd constructs tko-parse command with all necessary args
func tkoParseCmd(ctx context.Context, req TkoParseRequest) (*exec.Cmd, error) {
	if strings.TrimSpace(req.ResultsDir) == "" {
		return nil, fmt.Errorf("ResultsDir is empty")
	}
	if strings.TrimSpace(req.JobName) == "" {
		return nil, fmt.Errorf("JobName is empty")
	}
	args := []string{
		tkoParsePath,
		"--write-pidfile",
		req.ResultsDir,
		"--effective_job_name", req.JobName,
		"-l", "3",
		"--record-duration", "-r", "-o", "--suite-report",
	}
	cmd := exec.CommandContext(ctx, pythonPath, args...)
	return cmd, nil
}
