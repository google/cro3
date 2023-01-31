# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import importlib
import os

modules = glob.glob(__file__.replace("__init__", "[!_]*"))
__all__ = [os.path.basename(f).rpartition(".")[0] for f in modules]

supported_pns = {}
for mod in __all__:
    modp = getattr(
        importlib.import_module(f".{mod}", __package__), "SUPPORTED_PNS"
    )
    supported_pns = {**supported_pns, **modp}
