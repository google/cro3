# How to add a new gtest functional test

## Create a yaml file with test case details

Create a yaml file in your project for each gtest binary with format:

```yaml
---
author: "Chrome OS Team"
name: "CrosConfigTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "CheckName"
    tags: []
    criteria: "Fails if any of the following conditions occur:
                  1) Initialization of cros config fails
                  2) Name of the system (/ name) cannot be read or is invalid"

target_bin_location: "/usr/local/gtest/cros_config/cros_config_functional_test"
...
```

For gtest tests, the name is the suite name, and each case id is the name of the test case. This data will be used by testexecserver to generate unique ids for each case as well as how to execute each test case.

target_bin_location is required and will tell testexecserver where to find the binary on the DUT. This must match the installation location of the googletest binaries specified in the project ebuild.

## Add gtest tests to a build

Gtest tests will exist in various projects throughout the codebase. To simplify metadata generation, an eclass has been added to include into existing ebuilds that will facilitate googletest metadata generation.

Simply inherit the gtest eclass:

```bash
inherit gtest
```
Then set a variable specifying the location of the metadata files:

```bash
GTEST_METADATA=(
	libcros_config/cros_config_functional_test.yaml
  ...
)
```
Invoke the function to install the gtest_metadata:

```bash
src_install() {
    ...
    install_gtest_metadata "${GTEST_METADATA[@]}"
    ...
}
```

By default, gtest metadata is installed to /usr/local/build/gtest. This can be overwritten by specifying the following variable:

```bash
GTEST_METADATA_INSTALL_DIR=/some/new/dir
```
