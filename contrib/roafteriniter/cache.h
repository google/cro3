// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef _CACHE_H
#define _CACHE_H

#include <fcntl.h>
#include <pthread.h>
#include <semaphore.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <string.h>
#include <unistd.h>

#define SEM_NAME_MAX 25

/*
 * Lightweight file backed memory sharing across processes.
 */
struct __attribute__((packed)) cachehdr {
	uint64_t length;
	uint64_t count;
};

struct cache {
	int fd;
	sem_t *lock;    /* guard "hdr" */
	size_t size;
	struct cachehdr *hdr;
};

#define CACHE_DATA(c) ((char *)c->hdr + sizeof(struct cachehdr))
#define CACHE_ENDPTR(c) (CACHE_DATA(c) + c->hdr->length)

#define CACHE_OP_SUCCESS        (0)
#define CACHE_OPEN_FAILED       (1 << 0)
#define CACHE_FTRUNC_FAILED     (1 << 1)
#define CACHE_MAP_FAILED        (1 << 2)
#define CACHE_LOCK_INIT_FAILED  (1 << 3)
#define CACHE_INSERTION_SUCCESS (1 << 4)
#define CACHE_INSERTION_FAILED  (1 << 5)
#define CACHE_CONTAINS_SUCCESS  (1 << 6)
#define CACHE_CONTAINS_FAILED   (1 << 7)
#define CACHE_MUNMAP_FAILED	(1 << 8)
#define CACHE_CLOSE_FAILED	(1 << 9)
#define CACHE_SEMCLOSE_FAILED	(1 << 10)
#define CACHE_EINVAL		(1 << 11)

#define CACHE_OPEN_MODE (S_IRUSR|S_IWUSR|S_IRGRP|S_IWGRP|S_IROTH|S_IWOTH)

static inline void _cache_sync(struct cache *cache)
{
	msync(cache->hdr, cache->size, MS_SYNC|MS_INVALIDATE);
}

static inline int _cache_lock_init(struct cache *cache, const char *lockname)
{
	if ((cache->lock = sem_open(lockname, O_CREAT, 0666, 1)) == SEM_FAILED)
		return CACHE_LOCK_INIT_FAILED;

	return CACHE_OP_SUCCESS;
}

static inline void _cache_lock(struct cache *cache)
{
	sem_wait(cache->lock);
}

static inline void _cache_unlock(struct cache *cache)
{
	sem_post(cache->lock);
}

static inline struct cachehdr *_cache_map(int fd, size_t size)
{
	return (struct cachehdr *)mmap(NULL, size, PROT_READ|PROT_WRITE,
				       MAP_SHARED|MAP_POPULATE, fd, 0);
}

/* Expects cache->lock to be taken. */
static inline int _cache_contains(struct cache *cache, const char *item)
{
	char *ptr = NULL;
	ptr = CACHE_DATA(cache);
	while (*ptr) {
		if (!strcmp(ptr, item))
			return CACHE_CONTAINS_SUCCESS;
		ptr += strlen(ptr) + 1;
	}
	return CACHE_CONTAINS_FAILED;
}

/* Expects cache->lock to be taken. */
static inline int _cache_insert(struct cache *cache, const char *str)
{
	uint64_t copystart, copyend;
	char *ptr;
	size_t slen;

	if ((slen = strlen(str)) == 0)
		return CACHE_INSERTION_FAILED;

	ptr = CACHE_ENDPTR(cache);
	copyend = (uint64_t)ptr + slen + 1;
	copystart = (uint64_t)cache->hdr;

	if ((copyend < copystart) ||
	    ((copyend - copystart) > cache->size))
		return CACHE_INSERTION_FAILED;

	strncpy(ptr, str, strlen(str));
	cache->hdr->length += strlen(str) + 1;
	cache->hdr->count += 1;
	_cache_sync(cache);
	return CACHE_INSERTION_SUCCESS;
}

/*
 * cache_map - Map a cache file into memory.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 * @fname: path to file mapped into memory.
 * @lockname: path to semaphore.
 * @size: size of the memory mapping.
 *
 * Returns:
 *	CACHE_EINVAL: Invalid argument(s).
 *	CACHE_LOCK_INIT_FAILED: Unable to initialize semaphore.
 *	CACHE_OPEN_FAILED: Failed to open backing cache file.
 *	CACHE_FTRUNC_FAILED: Setting the size of backing cache failed.
 *	CACHE_MAP_FAILED: Failed to map backing cache file into memory.
 *	CACHE_OP_SUCCESS: Mapped cache into memory successfully.
 */
static inline int cache_map(struct cache *cache, const char *fname,
			    const char *lockname, size_t size)
{
	int ret;

	if (!cache || !fname || !lockname || size == 0 || (size % 0x1000))
		return CACHE_EINVAL;
	cache->size = size;

	if ((ret = _cache_lock_init(cache, lockname)) != CACHE_OP_SUCCESS)
		return ret;

	_cache_lock(cache);
	if ((cache->fd = open(fname, O_RDWR, CACHE_OPEN_MODE)) != -1) {
		if ((cache->hdr = _cache_map(cache->fd, cache->size)) == MAP_FAILED) {
			ret = CACHE_MAP_FAILED;
			goto close_fd;
		}
		ret = CACHE_OP_SUCCESS;
	} else if ((cache->fd = open(fname, O_RDWR|O_CREAT, CACHE_OPEN_MODE)) != -1) {
		if (ftruncate(cache->fd, cache->size) == -1) {
			ret = CACHE_FTRUNC_FAILED;
			goto close_fd;
		}
		if ((cache->hdr = _cache_map(cache->fd, cache->size)) == MAP_FAILED) {
			ret = CACHE_MAP_FAILED;
			goto close_fd;
		}

		memset(cache->hdr, 0, cache->size);
		cache->hdr->length = 0;
		cache->hdr->count = 0;
		_cache_sync(cache);
		ret = CACHE_OP_SUCCESS;
	} else {
		ret = CACHE_OPEN_FAILED;
	}
	_cache_unlock(cache);

	return ret;

close_fd:
	close(cache->fd);
	_cache_unlock(cache);

	return ret;
}

/*
 * cache_unmap - Unmap a cache file from memory.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 *
 * Returns:
 *	CACHE_EINVAL: Invalid argument(s).
 *
 *	Mask with corresponding bits set according to failure:
 *	CACHE_SEMCLOSE_FAILED: closing the semaphore failed.
 *	CACHE_MUNMAP_FAILED: unmapping the cache failed.
 *	CACHE_CLOSE_FAILED: closing the backing file fd failed.
 *	CACHE_OP_SUCCESS: successfully unmapped the cache.
 */
static inline int cache_unmap(struct cache *cache)
{
	int ret = CACHE_OP_SUCCESS;

	if (!cache)
		return CACHE_EINVAL;

	if (sem_close(cache->lock) == -1)
		ret |= CACHE_SEMCLOSE_FAILED;

	if (munmap(cache->hdr, cache->size) == -1)
		ret |= CACHE_MUNMAP_FAILED;

	if (close(cache->fd) == -1)
		ret |= CACHE_CLOSE_FAILED;

	return ret;
}

/*
 * cache_insert - Insert a string into cache.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 * @item: string to insert into cache.
 *
 * Returns:
 *	CACHE_EINVAL: invalid argument(s).
 *	CACHE_INSERTION_FAILED: item not found, insertion failed.
 *	CACHE_INSERTION_SUCCESS: item not found, insertion success.
 */
static inline int cache_insert(struct cache *cache, const char *item)
{
	int ret;

	if (!cache || !item)
		return CACHE_EINVAL;

	_cache_lock(cache);
	ret = _cache_insert(cache, item);
	_cache_unlock(cache);
	return ret;
}

/*
 * cache_debug_traverse - Traverse the cache and print out contents.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 */
static inline void cache_debug_traverse(struct cache *cache)
{
	char *ptr = NULL;

	if (!cache)
		return;

	_cache_lock(cache);
	ptr = CACHE_DATA(cache);
	while (*ptr) {
		printf("%s\n", ptr);
		ptr += strlen(ptr) + 1;
	}
	_cache_unlock(cache);
}

/*
 * cache_contains - Check if item is present in cache.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 * @item: item to check presence for in cache.
 *
 * Returns:
 *	CACHE_EINVAL: invalid argument(s).
 *	CACHE_CONTAINS_FAILED: item not found in cache.
 *	CACHE_CONTAINS_SUCCESS: item found in cache.
 */
static inline int cache_contains(struct cache *cache, const char *item)
{
	int ret;

	if (!cache || !item)
		return CACHE_EINVAL;

	_cache_lock(cache);
	ret = _cache_contains(cache, item);
	_cache_unlock(cache);
	return ret;
}

/*
 * cache_notcontains - Insert an item into cache if not present.
 *
 * @cache: struct cache instance representing memory mapped shared cache.
 * @item: item to insert into cache if not present.
 *
 * Returns:
 *	CACHE_EINVAL: invalid argument(s).
 *	CACHE_INSERTION_FAILED: item not found, insertion failed.
 *	CACHE_CONTAINS_SUCCESS: item already present in cache.
 *	CACHE_INSERTION_SUCCESS: item not found, insertion success.
 */
static inline int cache_notcontains_insert(struct cache *cache, const char *item)
{
	int ret;

	if (!cache || !item)
		return CACHE_EINVAL;

	_cache_lock(cache);
	if ((ret = _cache_contains(cache, item)) == CACHE_CONTAINS_FAILED)
		ret = _cache_insert(cache, item);
	_cache_unlock(cache);
	return ret;
}

#endif /* _CACHE_H */
