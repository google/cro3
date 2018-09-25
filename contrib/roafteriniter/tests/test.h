// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CONTRIB_ROAFTERINITER_TESTS_TEST_H_
#define CONTRIB_ROAFTERINITER_TESTS_TEST_H_

struct list_head {
    struct list_head *next, *prev;
};

struct testtype_A_NK {
    struct testtype_A_NK *ptr;
    struct list_head head;
    int a;
    char b;
};

void ptr_testtype_a_as_arg(struct testtype_A_NK*);
void testtype_a_as_arg(struct testtype_A_NK);

#endif  // CONTRIB_ROAFTERINITER_TESTS_TEST_H_
