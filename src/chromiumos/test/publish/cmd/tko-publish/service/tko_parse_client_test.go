package service

import (
	"context"
	"testing"
)

func TestTkoParseCmd_validateResultsDir(t *testing.T) {
	cmd, err := tkoParseCmd(context.Background(), TkoParseRequest{JobName: "aJob"})
	if err == nil {
		t.Fatalf("expect validation error: %v", cmd)
	}
}

func TestTkoParseCmd_validateJobName(t *testing.T) {
	cmd, err := tkoParseCmd(context.Background(), TkoParseRequest{ResultsDir: "/tmp/test"})
	if err == nil {
		t.Fatalf("expect validation error: %v", cmd)
	}
}

func TestTkoParseCmd_success(t *testing.T) {
	cmd, err := tkoParseCmd(context.Background(), TkoParseRequest{ResultsDir: "/tmp/test", JobName: "aJob"})
	if cmd == nil || cmd.Path == "" || len(cmd.Args) <= 1 {
		t.Fatalf("cmd doesn't look correct: %v", cmd)
	}
	if err != nil {
		t.Fatalf("unexpected error %v", err)
	}
}
