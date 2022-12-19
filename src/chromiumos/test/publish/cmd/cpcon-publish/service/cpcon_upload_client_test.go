package service

import (
	"context"
	"testing"
)

func TestUploadResultsCmd_validateResultsDir(t *testing.T) {
	cmd, err := uploadResultsCmd(context.Background(), CpconUploadRequest{})
	if err == nil {
		t.Fatalf("expect validation error: %v", cmd)
	}
}

func TestUploadResultsCmd_success(t *testing.T) {
	cmd, err := uploadResultsCmd(context.Background(), CpconUploadRequest{ResultsDir: "/tmp/test"})
	if cmd == nil || cmd.Path == "" || len(cmd.Args) <= 1 {
		t.Fatalf("cmd doesn't look correct: %v", cmd)
	}
	if err != nil {
		t.Fatalf("unexpected error %v", err)
	}
}
