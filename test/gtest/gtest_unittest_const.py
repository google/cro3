# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Ignore indention messages, since legacy scripts use 2 spaces instead of 4.
# pylint: disable=bad-indentation,docstring-section-indent
# pylint: disable=docstring-trailing-quotes

# Ignore line too long errors as many lines are large byte-arrays over 80 char
# pylint: disable=line-too-long
"""Consts used by the generate_gtest_metadata unit tests."""

###### VALID YAML DATA #######
VALID_YAML_SINGLE_CASE_NO_TAG = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_SINGLE_CASE_NO_TAG_PROTOBUF = b'\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_SINGLE_CASE_ONE_TAG = """---
author: "Existing Team"
name: "MyFakeTest2"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCaseX"
    tags: ["tag one"]
    criteria: "Just one tag"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_SINGLE_CASE_ONE_TAG_PROTOBUF = b'\n\x8b\x01\nA\n\x1d\n\x1bgtest.MyFakeTest2.FakeCaseX\x12\x15MyFakeTest2.FakeCaseX\x1a\t\n\x07tag one\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_SINGLE_CASE_MULTIPLE_TAGS = """---
author: "The Best Team"
name: "YetAnotherTest"
harness: "gtest"
category: "functional"
owners:
  - email: "myemail@chromium.org"


cases:
  - id: "AnotherFakeCase"
    tags: ["tag one", "two tag", "another tag", "this_tag", "my*tag", "your&tag"]
    criteria: "Single case with multiple tags"

target_bin_location: "/usr/bin/fake_test_path/test_binary"
...
"""
VALID_YAML_SINGLE_CASE_MULTIPLE_TAGS_PROTOBUF = b'\n\xd7\x01\n\x8f\x01\n&\n$gtest.YetAnotherTest.AnotherFakeCase\x12\x1eYetAnotherTest.AnotherFakeCase\x1a\t\n\x07tag one\x1a\t\n\x07two tag\x1a\r\n\x0banother tag\x1a\n\n\x08this_tag\x1a\x08\n\x06my*tag\x1a\n\n\x08your&tag\x12)\n\'"%\n#/usr/bin/fake_test_path/test_binary\x1a\x18\n\x16\n\x14myemail@chromium.org'

VALID_YAML_MULTIPLE_CASE_NO_TAG = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"
  - id: "FakeCase2"
    tags: []
    criteria: "Nothing special in case 2"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_MULTIPLE_CASE_NO_TAG_PROTOBUF = b'\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase2\x12\x14MyFakeTest.FakeCase2\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_MULTIPLE_CASE_ONE_TAG = """---
author: "Multi-Case Team"
name: "MultiCase_FakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "multiowners@google.com"
  - email: "secondowner@google.com"


cases:
  - id: "FakeCaseX"
    tags: ["tag one"]
    criteria: "Just one tag"
  - id: "FakeCaseY"
    tags: ["tag two"]
    criteria: "Just another single tag"

target_bin_location: "/tmp/test"
...
"""
VALID_YAML_MULTIPLE_CASE_ONE_TAG_PROTOBUF = b'\n\x98\x01\nO\n$\n"gtest.MultiCase_FakeTest.FakeCaseX\x12\x1cMultiCase_FakeTest.FakeCaseX\x1a\t\n\x07tag one\x12\x0f\n\r"\x0b\n\t/tmp/test\x1a4\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x98\x01\nO\n$\n"gtest.MultiCase_FakeTest.FakeCaseY\x12\x1cMultiCase_FakeTest.FakeCaseY\x1a\t\n\x07tag two\x12\x0f\n\r"\x0b\n\t/tmp/test\x1a4\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com'

VALID_YAML_MULTIPLE_CASE_MULTIPLE_TAGS = """---
author: "Multi-Case Team"
name: "MultiCase_FakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "multiowners@google.com"
  - email: "secondowner@google.com"
  - email: "thirdowner@chromium.org"


cases:
  - id: "FakeCaseX"
    tags: ["one tag", "two tag", "three tag", "four", "five tag", "six tag", "seven tag", "more"]
    criteria: "Just one tag"
  - id: "FakeCaseY"
    tags: ["tag one", "tag two"]
    criteria: "Just another single tag with random punctuation .afdk;jhg"
  - id: "FakeCaseZ"
    tags: ["one", "now", "never", "tag"]
    criteria: "Multi-tags"

target_bin_location: "/tmp/test/gtest/my_test"
...
"""
VALID_YAML_MULTIPLE_CASE_MULTIPLE_TAGS_PROTOBUF = b'\n\x8e\x02\n\x9b\x01\n$\n"gtest.MultiCase_FakeTest.FakeCaseX\x12\x1cMultiCase_FakeTest.FakeCaseX\x1a\t\n\x07one tag\x1a\t\n\x07two tag\x1a\x0b\n\tthree tag\x1a\x06\n\x04four\x1a\n\n\x08five tag\x1a\t\n\x07six tag\x1a\x0b\n\tseven tag\x1a\x06\n\x04more\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org\n\xcc\x01\nZ\n$\n"gtest.MultiCase_FakeTest.FakeCaseY\x12\x1cMultiCase_FakeTest.FakeCaseY\x1a\t\n\x07tag one\x1a\t\n\x07tag two\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org\n\xd4\x01\nb\n$\n"gtest.MultiCase_FakeTest.FakeCaseZ\x12\x1cMultiCase_FakeTest.FakeCaseZ\x1a\x05\n\x03one\x1a\x05\n\x03now\x1a\x07\n\x05never\x1a\x05\n\x03tag\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org'

VALID_YAML_EMPTY_TEST_BED_DEPS = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"
    testBedDependencies: []

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_EMPTY_TEST_BED_DEPS_PROTOBUF = b'\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_SINGLE_TEST_BED_DEPS = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"
    testBedDependencies: ["fakecat:fakevalue"]

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_SINGLE_TEST_BED_DEPS_PROTOBUF = b'\n\x93\x01\nI\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1"\x13\n\x11fakecat:fakevalue\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_MULTIPLE_TEST_BED_DEPS = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"
    testBedDependencies: ["fakecat:fakevalue", "anotherfakecat: anotherfakevalue", "carrier:verizon"]

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""
VALID_YAML_MULTIPLE_TEST_BED_DEPS_PROTOBUF = b'\n\xcb\x01\n\x80\x01\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1"\x13\n\x11fakecat:fakevalue""\n anotherfakecat: anotherfakevalue"\x11\n\x0fcarrier:verizon\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

VALID_YAML_ALL_FILES_PROTOBUF = b'\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n\x8b\x01\nA\n\x1d\n\x1bgtest.MyFakeTest2.FakeCaseX\x12\x15MyFakeTest2.FakeCaseX\x1a\t\n\x07tag one\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n\xd7\x01\n\x8f\x01\n&\n$gtest.YetAnotherTest.AnotherFakeCase\x12\x1eYetAnotherTest.AnotherFakeCase\x1a\t\n\x07tag one\x1a\t\n\x07two tag\x1a\r\n\x0banother tag\x1a\n\n\x08this_tag\x1a\x08\n\x06my*tag\x1a\n\n\x08your&tag\x12)\n\'"%\n#/usr/bin/fake_test_path/test_binary\x1a\x18\n\x16\n\x14myemail@chromium.org\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase2\x12\x14MyFakeTest.FakeCase2\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n\x98\x01\nO\n$\n"gtest.MultiCase_FakeTest.FakeCaseX\x12\x1cMultiCase_FakeTest.FakeCaseX\x1a\t\n\x07tag one\x12\x0f\n\r"\x0b\n\t/tmp/test\x1a4\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x98\x01\nO\n$\n"gtest.MultiCase_FakeTest.FakeCaseY\x12\x1cMultiCase_FakeTest.FakeCaseY\x1a\t\n\x07tag two\x12\x0f\n\r"\x0b\n\t/tmp/test\x1a4\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x8e\x02\n\x9b\x01\n$\n"gtest.MultiCase_FakeTest.FakeCaseX\x12\x1cMultiCase_FakeTest.FakeCaseX\x1a\t\n\x07one tag\x1a\t\n\x07two tag\x1a\x0b\n\tthree tag\x1a\x06\n\x04four\x1a\n\n\x08five tag\x1a\t\n\x07six tag\x1a\x0b\n\tseven tag\x1a\x06\n\x04more\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org\n\xcc\x01\nZ\n$\n"gtest.MultiCase_FakeTest.FakeCaseY\x12\x1cMultiCase_FakeTest.FakeCaseY\x1a\t\n\x07tag one\x1a\t\n\x07tag two\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org\n\xd4\x01\nb\n$\n"gtest.MultiCase_FakeTest.FakeCaseZ\x12\x1cMultiCase_FakeTest.FakeCaseZ\x1a\x05\n\x03one\x1a\x05\n\x03now\x1a\x07\n\x05never\x1a\x05\n\x03tag\x12\x1d\n\x1b"\x19\n\x17/tmp/test/gtest/my_test\x1aO\n\x18\n\x16multiowners@google.com\n\x18\n\x16secondowner@google.com\n\x19\n\x17thirdowner@chromium.org\n~\n4\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n\x93\x01\nI\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1"\x13\n\x11fakecat:fakevalue\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com\n\xcb\x01\n\x80\x01\n\x1c\n\x1agtest.MyFakeTest.FakeCase1\x12\x14MyFakeTest.FakeCase1"\x13\n\x11fakecat:fakevalue""\n anotherfakecat: anotherfakevalue"\x11\n\x0fcarrier:verizon\x12+\n)"\'\n%/usr/local/fake_test_path/test_binary\x1a\x19\n\x17\n\x15owneremail@google.com'

###### INVALID YAML DATA #######
INVALID_YAML_NO_AUTHOR = """---
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_NAME = """---
author: "New Team"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_HARNESS = """---
author: "New Team"
name: "MyFakeTest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CATEGORY = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_OWNERS = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"

cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_EMAIL = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - not_correct_field: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CASES = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CASE_ID = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - tags: []
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CASE_TAGS = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    criteria: "Nothing special"

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CASE_CRITERIA = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []

target_bin_location: "/usr/local/fake_test_path/test_binary"
...
"""

INVALID_YAML_NO_CASE_TARGET_LOC = """---
author: "New Team"
name: "MyFakeTest"
harness: "gtest"
category: "functional"
owners:
  - email: "owneremail@google.com"


cases:
  - id: "FakeCase1"
    tags: []
    criteria: "Nothing special"
...
"""