// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package publishserver

import (
	"fmt"
	"net"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"

	"chromiumos/lro"
)

// StartServer starts publish server on requested port
func (s *PublishService) StartServer(port int) error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return errors.Annotate(err, "Start publish server: failed to create listener at %d", port).Err()
	}

	s.manager = lro.New()
	defer s.manager.Close()
	server := grpc.NewServer()

	api.RegisterPublishServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.manager)

	s.logger.Println("Publish server is listening to request at ", l.Addr().String())
	return server.Serve(l)
}
