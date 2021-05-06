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
	api.UnimplementedTestServiceServer
	*lro.Manager
}

func (s *exampleServer) Serve(l net.Listener) error {
	s.Manager = lro.New()
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterTestServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	return server.Serve(l)
}

func (s *exampleServer) ProvisionDut(ctx context.Context, req *api.ProvisionDutRequest) (*longrunning.Operation, error) {
	op := s.Manager.NewOperation()
	go s.provision(ctx, req, op.Name)
	return op, nil
}

func (s *exampleServer) provision(ctx context.Context, req *api.ProvisionDutRequest, op string) {
	s.Manager.SetResult(op, &api.ProvisionDutResponse{})
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
