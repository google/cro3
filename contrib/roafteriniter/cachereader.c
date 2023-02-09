// Copyright 2018 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "./cache.h"

int main(int argc, const char *argv[]) {
  int ret;
  struct cache cache = {0};

  if (argc != 3) {
    fprintf(stderr, "USAGE: ./cachereader <cachefile> <lockname>\n");
    return -1;
  }

  if ((ret = cache_map(&cache, argv[1], argv[2], 50 * 0x1000) !=
             CACHE_OP_SUCCESS)) {
    fprintf(stderr, "cache_map failed with %d\n", ret);
    exit(-1);
  }

  cache_debug_traverse(&cache);

  cache_unmap(&cache);

  return 0;
}
