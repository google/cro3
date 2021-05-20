package lro_test

import (
	"context"
	"net"
	"testing"

	"chromiumos/lro"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

type exampleServer struct {
	api.UnimplementedExecutionServiceServer
	*lro.Manager
}

func (s *exampleServer) Serve(l net.Listener) error {
	s.Manager = lro.New()
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterExecutionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	return server.Serve(l)
}

func (s *exampleServer) RunTests(ctx context.Context, req *api.RunTestsRequest) (*longrunning.Operation, error) {
	op := s.Manager.NewOperation()
	go s.RunTests(ctx, req)
	return op, nil
}

func RunServer() {
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		panic(err)
	}
	s := exampleServer{}
	if err := s.Serve(l); err != nil {
		panic(err)
	}
}

func TestServe(t *testing.T) {
	go RunServer()
	// TODO(shapiroc): Add testing
}
