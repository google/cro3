// Copyright 2018 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "test.h"

#define __init __attribute__((__section__(".init.text")))
#define __initdata __attribute__((__section__(".init.data")))
#define __ro_after_init __attribute__((__section__(".data..ro_after_init")))

struct testtype_B_NK {
	struct testtype_B_NK *next;
	struct list_head head;
	int d;
	char e;
	char *f;
};

struct testtype_C_OK {
	int a;
	char b;
};

struct testtype_D_OK {
	struct testtype_D_OK **ptr2ptr;
};

struct mutex {
	int val;
	struct list_head wait_list;
};

struct testtype_E_NK {
	struct mutex mutexobj;
};

struct rb_node {
	struct rb_node *left, *right;
};

struct rb_root {
	struct rb_node *rb_node;
};

struct testtype_F_NK {
	struct rb_node blah;
};

struct testtype_FF_NK {
	struct rb_root *root;
};

typedef struct {
	int counter;
} atomic_t;

typedef struct refcount_struct {
	atomic_t refs;
} refcount_t;

struct testtype_G_NK {
	refcount_t refcount;
};

struct testtype_G2_NK {
	struct refcount_struct refstr;
};

struct testtype_H_OK {
	int a;
	int b;
	char c;
};

struct testtype_I_OK {
	int a;
	int b;
	char c;
};

typedef unsigned long resource_size_t;
struct resource {
	resource_size_t start;
	resource_size_t end;
	const char *name;
	unsigned long flags;
	unsigned long desc;
	struct resource *parent, *sibling, *child;
};

static struct testtype_A_NK global_objA;
static struct list_head global_listhead;
static struct testtype_A_NK global_objA2;
static struct testtype_B_NK global_objB;
static struct testtype_C_OK global_objC;
static struct testtype_C_OK global_ns_objC;
static struct testtype_D_OK global_objD;
static struct mutex global_mutexobj;
static struct testtype_E_NK global_objE;
static struct testtype_F_NK global_objF;
static struct testtype_FF_NK global_objFF;
static refcount_t global_refcountt;
static struct refcount_struct global_objref;
static struct testtype_G_NK global_objG;
static struct testtype_G2_NK global_objG2;
struct testtype_G2_NK global_objG22;
struct testtype_H_OK global_objH;
struct testtype_I_OK global_objI __initdata;
struct testtype_I_OK global_objII __ro_after_init;
static struct resource resource_obj;

void __init blah(void)
{
	global_ns_objC.a = 123;
	global_ns_objC.b = 'c';

	global_objH.a = 234;
	global_objH.b = 345;
	global_objH.c = 'z';

	global_objI.a = 123;
	global_objI.b = 456;
	global_objI.c = 'a';

	global_objII.a = 123;
	global_objII.b = 456;
	global_objII.c = 'a';
}

int main(int argc, const char *argv[])
{
	struct testtype_B_NK obj_b = {
		.d = 10,
		.e = 'b',
		.f = (void *)0,
	};
	struct testtype_A_NK obj_a = {
		.a = 11,
		.b = 'a',
	};

	global_ns_objC.a = 567;
	global_ns_objC.b = 'd';

	return 0;
}
