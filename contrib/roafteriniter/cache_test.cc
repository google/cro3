// Copyright 2018 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <gtest/gtest.h>

extern "C" {
#include "./cache.h"
}

#define TESTCACHEFILE "/tmp/testcache"
#define TESTLOCKNAME "/testcachelock"

class CacheTest : public ::testing::Test {
 protected:
        struct cache cache;

        void SetUp() override {
            memset(&cache, 0, sizeof(struct cache));
            remove(TESTCACHEFILE);
            ASSERT_EQ(CACHE_OP_SUCCESS, cache_map(&cache, TESTCACHEFILE,
                        TESTLOCKNAME, 0x1000));
        }

        void TearDown() override {
            ASSERT_EQ(CACHE_OP_SUCCESS, cache_unmap(&cache));
            remove(TESTCACHEFILE);
        }
};

TEST_F(CacheTest, InsertFromTwoProcesses) {
    const int child_insertions_cnt = 15;
    const int parent_insertions_cnt = 10;

    if (fork() == 0) {
        struct cache cache2 = {0};
        cache_map(&cache2, TESTCACHEFILE, TESTLOCKNAME, 0x1000);
        for (int i = 0; i < child_insertions_cnt; i++)
            EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_insert(
                                                &cache2, "AAAAA"));
        cache_unmap(&cache2);
        exit(0);
    } else {
        for (int i = 0; i < parent_insertions_cnt; i++)
            EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_insert(
                                                &cache, "BBBBBB"));
    }

    wait(NULL);
    EXPECT_EQ(child_insertions_cnt+parent_insertions_cnt, cache.hdr->count);
}

TEST_F(CacheTest, CacheContainsFails) {
    EXPECT_EQ(CACHE_CONTAINS_FAILED, cache_contains(&cache, "AAAAAAA"));
}

TEST_F(CacheTest, CacheContainsSucceeds) {
    EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_insert(&cache, "AAAAAAA"));
    EXPECT_EQ(CACHE_CONTAINS_SUCCESS, cache_contains(&cache, "AAAAAAA"));
}

TEST_F(CacheTest, CacheContainsAcrossProcess) {
    if (fork() == 0) {
        struct cache cache2 = {0};
        cache_map(&cache2, TESTCACHEFILE, TESTLOCKNAME, 0x1000);
        EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_insert(&cache2, "AAAAAAA"));
        cache_unmap(&cache2);
        exit(0);
    }

    wait(NULL);
    EXPECT_EQ(CACHE_CONTAINS_SUCCESS, cache_contains(&cache, "AAAAAAA"));
}

TEST_F(CacheTest, CacheInsertIfNotContains) {
    cache_insert(&cache, "AAAAAAA");
    EXPECT_EQ(CACHE_CONTAINS_SUCCESS, cache_notcontains_insert(
                                                    &cache, "AAAAAAA"));
    EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_notcontains_insert(
                                                    &cache, "BBBBBBB"));
}

TEST_F(CacheTest, InsertZeroLengthFails) {
    EXPECT_EQ(CACHE_INSERTION_FAILED, cache_insert(&cache, ""));
}

TEST_F(CacheTest, CacheHeaderSize) {
    EXPECT_EQ(sizeof(struct cachehdr), 16);
}

TEST_F(CacheTest, InsertFailsLengthExceeded) {
    int insert_count = (0x1000 - sizeof(struct cachehdr)) / 4;

    for (int i = 0; i < insert_count; i++)
        cache_insert(&cache, "AAA");

    EXPECT_EQ(CACHE_INSERTION_FAILED, cache_insert(&cache, "A"));
}

TEST_F(CacheTest, InsertFailsLengthExceededAcrossProcesses) {
    int insert_count = (0x1000 - sizeof(struct cachehdr)) / 4;

    if (fork() == 0) {
        struct cache cache2 = {0};
        cache_map(&cache2, TESTCACHEFILE, TESTLOCKNAME, 0x1000);
        for (int i = 0; i < insert_count/2; i++)
            cache_insert(&cache2, "AAA");
        cache_unmap(&cache2);
        exit(0);
    }

    for (int i = 0; i < insert_count/2; i++)
        EXPECT_EQ(CACHE_INSERTION_SUCCESS, cache_insert(&cache, "AAA"));

    wait(NULL);
    EXPECT_EQ(CACHE_INSERTION_FAILED, cache_insert(&cache, "A"));
}

TEST_F(CacheTest, MapInvalidCache) {
    EXPECT_EQ(CACHE_EINVAL, cache_map(NULL, TESTCACHEFILE,
                                      TESTCACHEFILE, 0x1000));
}

TEST_F(CacheTest, MapInvalidCacheFile) {
    struct cache cache2 = {0};
    EXPECT_EQ(CACHE_EINVAL, cache_map(&cache2, NULL, TESTCACHEFILE, 0x1000));
}

TEST_F(CacheTest, MapInvalidCacheLock) {
    struct cache cache2 = {0};
    EXPECT_EQ(CACHE_EINVAL, cache_map(&cache2, TESTCACHEFILE, NULL, 0x1000));
}

TEST_F(CacheTest, MapInvalidCacheSize) {
    struct cache cache2 = {0};
    EXPECT_EQ(CACHE_EINVAL, cache_map(&cache2, TESTCACHEFILE,
                                      TESTCACHEFILE, 0));
}

TEST_F(CacheTest, UnmapInvalidCache) {
    EXPECT_EQ(CACHE_EINVAL, cache_unmap(NULL));
}

TEST_F(CacheTest, InsertInvalidCache) {
    EXPECT_EQ(CACHE_EINVAL, cache_insert(NULL, "AAA"));
}

TEST_F(CacheTest, InsertNull) {
    EXPECT_EQ(CACHE_EINVAL, cache_insert(&cache, NULL));
}

TEST_F(CacheTest, ContainsInvalidCache) {
    EXPECT_EQ(CACHE_EINVAL, cache_contains(NULL, "AAA"));
}

TEST_F(CacheTest, ContainsInvalidNull) {
    EXPECT_EQ(CACHE_EINVAL, cache_contains(&cache, NULL));
}

GTEST_API_ int main(int argc, char *argv[]) {
    int ret;

    remove(TESTCACHEFILE);
    ::testing::InitGoogleTest(&argc, argv);
    ret = RUN_ALL_TESTS();
    if (ret == 0)
        printf("[+] Cache tests succeeded\n");
    else
        printf("[x] Cache tests failed\n");

    return ret;
}
