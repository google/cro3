// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package servodserver

import (
	"fmt"
	"net"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"

	"chromiumos/lro"
)

// StartServer starts servod server on requested port
func (s *ServodService) StartServer(port int32) error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return errors.Annotate(err, "Start servod server: failed to create listener at %d", port).Err()
	}

	s.manager = lro.New()
	defer s.manager.Close()
	server := grpc.NewServer()

	api.RegisterServodServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.manager)

	s.logger.Println("Servod server is listening to request at ", l.Addr().String())
	return server.Serve(l)
}
