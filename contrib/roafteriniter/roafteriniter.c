// Copyright 2018 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/* Includes */
#include "cache.h"
#include "gcc-common.h"

/* Macros */
#define STAGE1_INT "/tmp/rai_int"
#define STAGE1_CHK "/tmp/rai_chk"
#define STAGE2_FINAL "/tmp/rai_final"
#define LINELEN 100

#define STAGE1_PG_COUNT 30
#define STAGE2_PG_COUNT 60

#define __init ".init.text"
#define __initdata ".init.data"
#define __ro_after_init ".data..ro_after_init"

#define IS_RECORD_TYPE(T) (TREE_CODE(T) == RECORD_TYPE)
#define FOR_EACH_STRUCT_MEMBER(T, MEM) \
  for (MEM = TYPE_VALUES((T)); (MEM); MEM = TREE_CHAIN(MEM))
#define FOR_EACH_ATTR_VALUE(SEC, AV) \
  for (AV = TREE_VALUE((SEC)); (AV); AV = TREE_CHAIN(AV))

#define PASS_NAME roafteriniter
#define NO_WRITE_SUMMARY
#define NO_GENERATE_SUMMARY
#define NO_READ_SUMMARY
#define NO_READ_OPTIMIZATION_SUMMARY
#define NO_WRITE_OPTIMIZATION_SUMMARY
#define NO_STMT_FIXUP
#define NO_FUNCTION_TRANSFORM
#define NO_VARIABLE_TRANSFORM
#define NO_GATE

/* GCC Callbacks */
__visible int plugin_init(struct plugin_name_args *,
                          struct plugin_gcc_version *);
static unsigned int roafteriniter_execute(void);
static void rai_callback_finish(void *, void *);

/* Local GCC helper include(Needs to be placed after some macros,
 * callbacks).
 */
#include "gcc-generate-gimple-pass.h"

/* Static declarations */
static struct cache interesting, checked, results;
static const char *blacklisted_typenames[] = {
    "atomic_t",     "atomic64_t", "arch_spinlock_t", "spinlock_t", "cpumask_t",
    "sk_buff_head", NULL};

static bool stage2 = false;

static void die(const char *format, ...);
static void rai_map_cache(void);
static const char *rai_structtype_str(tree);
static bool rai_check_interesting_sttype(tree, const char *);
static bool rai_hardcoded_blacklist_typename(const char *);
static bool rai_interesting_struct_type(tree);
static void rai_stage1_execute(void);
static bool is_global(tree);
static bool is_fn_annotated(tree);
static bool is_var_annotated(tree);
static void rai_check_assign_stmt(gimple);
static void rai_stage2_execute(void);

/* Externs */
__visible int plugin_is_GPL_compatible = 1;

__visible int plugin_init(struct plugin_name_args *info,
                          struct plugin_gcc_version *ver __unused) {
  int i;
  const char *plugin_name = info->base_name;
  const int argc = info->argc;
  struct plugin_argument *argv = info->argv;

  PASS_INFO(roafteriniter, "ssa", 1, PASS_POS_INSERT_AFTER);

  for (i = 0; i < argc; i++) {
    if (!(strcmp(argv[i].key, "stage2"))) {
      stage2 = true;
      continue;
    }
    fprintf(stderr, "unknown plugin option(%s)\n", argv[i].key);
    return -1;
  }

  /* Map cache */
  rai_map_cache();

  register_callback(plugin_name, PLUGIN_PASS_MANAGER_SETUP, NULL,
                    &roafteriniter_pass_info);
  register_callback(plugin_name, PLUGIN_FINISH, rai_callback_finish, NULL);

  return 0;
}

/* Static definitions */
static void die(const char *format, ...) {
  va_list vargs;
  va_start(vargs, format);
  fprintf(stderr, "FAILURE: ");
  vfprintf(stderr, format, vargs);
  fprintf(stderr, "\n");
  va_end(vargs);
  exit(-1);
}

/*
 * rai_map_cache - Map cache files into memory.
 *
 * The following cache files are mapped into memory:
 *	- STAGE1_INT   : Cache holding struct types that are considered
 *interesting.
 *	- STAGE1_CHK   : Cache holding struct types that have been checked for
 *whether they are interesting or not.
 *	- STAGE2_FINAL : Cache holding log entries corresponding to writes to
 *instances of interesting struct types.
 */
static void rai_map_cache(void) {
  int ret;
  if ((ret = cache_map(&interesting, STAGE1_INT, "/int",
                       STAGE1_PG_COUNT * 0x1000) != CACHE_OP_SUCCESS))
    die("cache_map() returned %d at %d", ret, __LINE__);

  if (!stage2 &&
      (ret = cache_map(&checked, STAGE1_CHK, "/chk",
                       STAGE1_PG_COUNT * 0x1000) != CACHE_OP_SUCCESS))
    die("cache_map() returned %d at %d", ret, __LINE__);

  if (stage2 && (ret = cache_map(&results, STAGE2_FINAL, "/final",
                                 STAGE2_PG_COUNT * 0x1000) != CACHE_OP_SUCCESS))
    die("cache_map() returned %d at %d", ret, __LINE__);
}

/*
 * rai_structtype_str - Return the name of the struct type.
 *
 * @type_tree: tree node corresponding to the RECORD type or struct instance.
 *
 * Returns:
 *	const char* representing struct instance name or struct type name. If
 *the typename is a typedef, return the typedef.
 */
static const char *rai_structtype_str(tree type_tree) {
  tree name_tree;

  if (!type_tree) return NULL;

  if (!(name_tree = TYPE_NAME(type_tree))) return NULL;

  if (TREE_CODE(name_tree) == IDENTIFIER_NODE)
    return IDENTIFIER_POINTER(name_tree);
  else if (TREE_CODE(name_tree) == TYPE_DECL && DECL_NAME(name_tree))
    return IDENTIFIER_POINTER(DECL_NAME(name_tree));

  return NULL;
}

/*
 * rai_check_interesting_sttype - Check if a struct type is interesting.
 *
 * The following struct types will be considered not interesting given that
 * `struct A` is not interesting.
 *
 * struct B {
 *	struct A a;	// non-interesting as `struct A` is non-interesting.
 * };
 * struct C {
 *	struct A *a_ptr; // non-interesting as `struct A` is non-interesting.
 * };
 * struct D {
 *	struct B *b;	// non-interesting as `struct B` is non-interesting.
 * };
 * struct E {
 *	struct C c;	// non-interesting as `struct C` is non-interesting.
 * };
 * struct F {
 *	struct F *f;	// non-interesting as contains pointer to its own type.
 * };
 *
 * @type_tree: tree node corresponding to a struct type.
 * @type_name: string representation of the struct type name.
 */
static bool rai_check_interesting_sttype(tree type_tree,
                                         const char *type_name) {
  tree member;
  bool has_fields = false;
  gcc_assert(TREE_CODE(type_tree) == RECORD_TYPE);

  /* (1) Iterate through each member of the struct type. Investigate each
   * member for properties that might make this struct type non-interesting. */
  FOR_EACH_STRUCT_MEMBER(type_tree, member) {
    has_fields = true;
    gcc_assert(TREE_CODE(member) == FIELD_DECL);

    /* (1.1) Check if the member is a pointer to something. */
    tree member_tree = TREE_TYPE(member);
    if (TREE_CODE(member_tree) == POINTER_TYPE) {
      /* (1.1.1) If it is a pointer to a non-RECORD type, we cannot
       * infer anything useful from it. So continue onto the next member. */
      tree member_type = TREE_TYPE(member_tree);
      if (TREE_CODE(member_type) != RECORD_TYPE) continue;

      /* (1.1.2) If it is an anonymous struct, we cannot infer anything useful
       * from it. So continue onto the next member. */
      const char *member_typename = rai_structtype_str(member_type);
      if (!member_typename) continue;

      /* (1.1.3) If it is a pointer to a RECORD type, check if it is a pointer
       * to itself. If so, this struct type is deemed as not interesting. */
      /* (1.1.4) If it is a pointer to a RECORD type, check if the RECORD type
       * is interesting. If it is not interesting, then this struct
       * type will also be deemed as not interesting. */
      if (!strcmp(member_typename, type_name) ||
          !rai_interesting_struct_type(member_type))
        return false;

      /* (1.2) Check if the member is an instance of another non-interesting
       * struct type. If so, return false. */
    } else if (TREE_CODE(member_tree) == RECORD_TYPE &&
               !rai_interesting_struct_type(member_tree)) {
      return false;
    }
  }

  /* If we are unable to iterate through the fields of the RECORD_TYPE
   * deem the struct type to be non-interesting. */
  if (!has_fields) return false;

  return true;
}

/*
 * rai_hardcoded_blacklist_typename - check if type_name is a blacklisted type.
 *
 * @type_name: string representation of a type.
 *
 * Returns:
 *	true: if type_name is present in blacklisted_typenames.
 *	false: otherwise.
 */
static bool rai_hardcoded_blacklist_typename(const char *type_name) {
  const char **tmp;

  if (!type_name) return false;

  for (tmp = blacklisted_typenames; *tmp; tmp++)
    if (!strcmp(*tmp, type_name)) return true;
  return false;
}

static bool rai_interesting_struct_type(tree type_tree) {
  const char *type_name;
  int ret;

  if (!IS_RECORD_TYPE(type_tree)) return false;

  type_name = rai_structtype_str(type_tree);
  if (!type_name) return false;

  /* If type_name is already categorized as interesting, return true */
  if (cache_contains(&interesting, type_name) == CACHE_CONTAINS_SUCCESS)
    return true;

  /* If type_name is already checked, return. Else insert and continue */
  ret = cache_notcontains_insert(&checked, type_name);
  if (ret == CACHE_CONTAINS_SUCCESS) return false;

  if (ret == CACHE_INSERTION_FAILED)
    die("cache_notcontains_insert() returned %d at %d", ret, __LINE__);

  if (rai_hardcoded_blacklist_typename(type_name)) return false;

  if (rai_check_interesting_sttype(type_tree, type_name)) {
    ret = cache_notcontains_insert(&interesting, type_name);
    if (ret == CACHE_INSERTION_FAILED)
      die("cache_notcontains_insert() returned %d at %d\n", ret, __LINE__);
    return true;
  } else {
    return false;
  }

  return true;
}

/*
 * rai_stage1_execute - Entry point of plugin stage 1.
 *
 * In stage 1, the plugin iterates over each global variable in a translation
 * unit and determines if its type is interesting.
 */
static void rai_stage1_execute(void) {
  varpool_node_ptr node;

  FOR_EACH_VARIABLE(node) {
    tree var_node = NODE_DECL(node);
    gcc_assert(TREE_CODE(var_node) == VAR_DECL);

    tree type_tree;
    type_tree = TREE_TYPE(var_node);
    rai_interesting_struct_type(type_tree);
  }
}

/*
 * is_global - Returns true if var_tree corresponds to a global variable.
 */
static bool is_global(tree var_tree) {
  varpool_node_ptr node;

  FOR_EACH_VARIABLE(node) {
    tree var_node = NODE_DECL(node);
    gcc_assert(TREE_CODE(var_node) == VAR_DECL);
    if (var_node == var_tree) return true;
  }

  return false;
}

/*
 * is_annotated - Returns true of the declaration is annotated.
 *
 * @decl: tree node representing variable or function.
 * @sname: annotation to check on decl
 */
static bool is_annotated(tree decl, const char *sname) {
  tree section, attr_value;

  section = lookup_attribute("section", DECL_ATTRIBUTES(decl));
  if (!section || !TREE_VALUE(section)) return false;

  FOR_EACH_ATTR_VALUE(section, attr_value) {
    const char *str = TREE_STRING_POINTER(TREE_VALUE(attr_value));
    if (!strncmp(str, sname, strlen(sname))) return true;
  }

  return false;
}

/*
 * is_fn_annotated: Returns true if a function is annotated with __init.
 *
 * @var_decl: tree node representing a variable.
 */
static bool is_fn_annotated(tree var_decl) {
  return is_annotated(var_decl, __init);
}

/*
 * is_var_annotated: Returns true if a variable declaration is annotated with
 *		     either __initdata or __ro_after_init.
 *
 * @var_decl: tree node representing a function.
 */
static bool is_var_annotated(tree var_decl) {
  return is_annotated(var_decl, __initdata) ||
         is_annotated(var_decl, __ro_after_init);
}

/*
 * rai_check_assign_stmt: Investigate an assignment statement.
 *
 * Given a gimple statement, write a log entry to STAGE2_FINAL iff the
 * following conditions are met.
 * - The write is to an instance of an interesting struct type.
 * - The write is to a global variable that is not already annotated.
 *
 * A single line of the log entry will have the following information.
 * - name of struct instance whose member is being written to.
 * - name of struct type corresponding to the instance.
 * - function name within which the write occurs.
 * - whether or not the function is annotated with __init.
 *
 * int a;
 * struct sometype {
 *	int b;
 * };
 * struct sometype st;
 *
 * void func1(void) {
 *	a = 10;
 *	st.b = 123;
 * }
 *
 * void __init func2(void) {
 *     st.b = 234;
 * };
 *
 * In the above example, `struct sometype` is interesting. The following log
 * records(without quotes) will be written to STAGE2_FINAL.
 * "v:st t:sometype fn:func1 status:NK"
 * "v:st t:sometype fn:func2 status:OK"
 *
 * The status fields correspond to whether or not they were written to from a
 * function annotated with __init.
 *
 * @stmt: statement to check for a write.
 */
static void rai_check_assign_stmt(gimple stmt) {
  tree lhs, arg0, arg0_type;
  char buffer[LINELEN];
  int ret;

  lhs = gimple_assign_lhs(stmt);
  if (TREE_CODE(lhs) != COMPONENT_REF) return;

  arg0 = TREE_OPERAND(lhs, 0);
  if (TREE_CODE(arg0) != VAR_DECL) return;

  if (!is_global(arg0) || is_var_annotated(arg0)) return;

  arg0_type = TREE_TYPE(arg0);
  if (TREE_CODE(arg0_type) != RECORD_TYPE) return;

  if (cache_contains(&interesting, rai_structtype_str(arg0_type)) ==
      CACHE_CONTAINS_FAILED)
    return;

  memset(buffer, 0, LINELEN);
  snprintf(buffer, LINELEN - 1, "v:%s t:%s fn:%s status:%s",
           IDENTIFIER_POINTER(DECL_NAME(arg0)), rai_structtype_str(arg0_type),
           DECL_NAME_POINTER(current_function_decl),
           is_fn_annotated(current_function_decl) ? "OK" : "NK");
  if ((ret = cache_notcontains_insert(&results, buffer)) ==
      CACHE_INSERTION_FAILED) {
    die("cache_notcontains_insert() returned %d at %d\n", ret, __LINE__);
    exit(-1);
  }
}

/*
 * rai_stage2_execute: Entry point plugin stage 2.
 *
 * In stage 2 the plugin iterates over each statement of each basic block
 * of each function in a translation unit, and processes GIMPLE_ASSIGN
 * statements.
 */
static void rai_stage2_execute(void) {
  basic_block bb;

  FOR_ALL_BB_FN(bb, cfun) {
    gimple_stmt_iterator gsi;
    for (gsi = gsi_start_bb(bb); !gsi_end_p(gsi); gsi_next(&gsi)) {
      gimple stmt = gsi_stmt(gsi);
      if (gimple_code(stmt) == GIMPLE_ASSIGN) rai_check_assign_stmt(stmt);
    }
  }
}

/* Callback definitions */
static unsigned int roafteriniter_execute(void) {
  if (!stage2)
    rai_stage1_execute();
  else
    rai_stage2_execute();

  return 0;
}

/*
 * rai_callback_finish: Unmap the caches from memory.
 */
static void rai_callback_finish(void *event_data __unused,
                                void *user_data __unused) {
  cache_unmap(&interesting);
  if (!stage2) cache_unmap(&checked);
  if (stage2) cache_unmap(&results);
}
