package lro_test

import (
	"context"
	"net"

	"infra/libs/lro"

	"go.chromium.org/chromiumos/config/go/api/test/tls"
	"go.chromium.org/chromiumos/config/go/api/test/tls/dependencies/longrunning"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type exampleServer struct {
	tls.UnimplementedCommonServer
	*lro.Manager
}

func (s *exampleServer) Serve(l net.Listener) error {
	s.Manager = lro.New()
	defer s.Manager.Close()
	server := grpc.NewServer()
	tls.RegisterCommonServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	return server.Serve(l)
}

func (s *exampleServer) ProvisionDut(ctx context.Context, req *tls.ProvisionDutRequest) (*longrunning.Operation, error) {
	op := s.Manager.NewOperation()
	go s.provision(ctx, req, op.Name)
	return op, nil
}

func (s *exampleServer) provision(ctx context.Context, req *tls.ProvisionDutRequest, op string) {
	if req.GetName() != "some host" {
		s.Manager.SetError(op, status.Newf(codes.NotFound, "Unknown DUT %s", req.GetName()))
		return
	}
	s.Manager.SetResult(op, &tls.ProvisionDutResponse{})
}

func Example() {
	l, err := net.Listen("tcp", ":0")
	if err != nil {
		panic(err)
	}
	s := exampleServer{}
	if err := s.Serve(l); err != nil {
		panic(err)
	}
}
