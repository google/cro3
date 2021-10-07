// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package provisionserver

import (
	"fmt"
	"net"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"

	"chromiumos/lro"
)

// startServer starts provision server on requested port.
func (s *provision) StartServer(port int) error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return errors.Annotate(err, "start server: create listener at %d", port).Err()
	}
	s.manager = lro.New()
	defer s.manager.Close()
	server := grpc.NewServer()
	api.RegisterProvisionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.manager)
	s.logger.Println("provisionservice listen to request at ", l.Addr().String())
	return server.Serve(l)
}
