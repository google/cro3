package service

import (
	"testing"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"
)

func TestUnpackMetadata_success(t *testing.T) {
	jobName := "aJob"
	anyMetadata, _ := anypb.New(&api.PublishTkoMetadata{JobName: jobName})
	req := api.PublishRequest{
		Metadata: anyMetadata,
	}
	m, err := unpackMetadata(&req)
	if m.JobName != jobName {
		t.Fatalf("jobName mismatch %s expected %s", m.JobName, jobName)
	}
	if err != nil {
		t.Fatalf("error when unpack metadata")
	}
}

func TestUnpackMetadata_invalidRequest(t *testing.T) {
	anyMetadata, _ := anypb.New(&api.PublishGcsMetadata{})
	req := api.PublishRequest{
		Metadata: anyMetadata,
	}
	m, err := unpackMetadata(&req)
	if m.JobName != "" {
		t.Fatalf("expect empty unpacked metadata")
	}
	if err == nil {
		t.Fatalf("expect error for invalid request")
	}
}
