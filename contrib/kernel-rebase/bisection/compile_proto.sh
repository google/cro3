#!/bin/bash
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

python3 -m grpc_tools.protoc --python_out=. --pyi_out=. --grpc_python_out=. --proto_path=. kbuild_dispatcher.proto
python3 -m grpc_tools.protoc --python_out=. --pyi_out=. --grpc_python_out=. --proto_path=. kbuild_builder.proto
