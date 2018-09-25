# Roafteriniter

A GCC plugin that looks for `__ro_after_init` candidates as part of the
kernel build process.

## Usage
* Install the GCC plugin-dev package. If you are on GCC 7 do:
```bash
$ apt-get install gcc-7-plugin-dev
```

* Build the plugin and (optionally)run tests. Run the `arm64_test`
  target if you have an ARM64 cross compiler installed and present in
$PATH.
```bash
$ make
$ GTEST_LIBPATH=<path-to-libgtest.so> GTEST_INCDIR=<path-to-gtest-headers> make ctest
$ make test
$ make arm64_test
```

* Run both stages of the plugin on a kernel of your choice.
```bash
$ make clean && KDIR=<path-to-kernel-directory> make kern
```

## Stages
When `make kern` is run, the following steps occur.

* Stage 1 of the plugin is run. The kernel is built with `allmodconfig`,
  and a list of interesting types is written out to `/tmp/rai_int`. All
checked types are written out to `/tmp/rai_chk`.

* Stage 2 of the plugin is run. For each memory write into a variable of
  type listed in `/tmp/rai_int`, write an entry into `/tmp/rai_final`.
This entry will contain the variable name, the typename, the function
from which this write occured, and whether or not this function is
annotated with `__init`.

* At this stage, the plugins have done their work. All that remains is
  to process the log(`/tmp/rai_final`) written out by the plugin. Use `cachereader` to
print out the entries in a readable form, and `postprocess.py` to list
out all variable names to which a write exists only from functions
marked annotated with `__init`.
