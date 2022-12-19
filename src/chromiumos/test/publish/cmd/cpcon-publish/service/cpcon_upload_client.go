package service

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
)

// Path to python binary inside the container.
const pythonPath = "/usr/local/bin/python3"

// Path to upload results script inside the container.
const uploadResultsPath = "/usr/local/autotest/contrib/upload_results.py"

// CpconUploadRequest holds information needed by upload_results.py script
type CpconUploadRequest struct {
	// Path to test results to upload
	ResultsDir string
}

// uploadResultsCmd constructs upload_results command with all necessary args
func uploadResultsCmd(ctx context.Context, req CpconUploadRequest) (*exec.Cmd, error) {
	if strings.TrimSpace(req.ResultsDir) == "" {
		return nil, fmt.Errorf("ResultsDir is empty")
	}
	args := []string{
		uploadResultsPath,
		"upload", "-d",
		req.ResultsDir,
	}
	cmd := exec.CommandContext(ctx, pythonPath, args...)
	return cmd, nil
}
