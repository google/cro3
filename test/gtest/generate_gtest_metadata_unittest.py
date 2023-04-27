#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Ignore indention messages, since legacy scripts use 2 spaces instead of 4.
# pylint: disable=bad-indentation,docstring-section-indent
# pylint: disable=docstring-trailing-quotes
# pylint: disable=line-too-long

# Ignore line too long errors as many lines are large byte-arrays over 80 char
# pylint: disable=line-too-long

# Ignore protected member access as these are unit tests explicitly accessing
# pylint: disable=protected-access

"""Unit tests for generate_gtest_metadata.py script"""

import collections
from unittest import main
from unittest import mock
from unittest import TestCase

from chromiumos.test.api import test_case_metadata_pb2 as tc_metadata_pb
from chromiumos.test.api import test_case_pb2 as tc_pb
from chromiumos.test.api import test_harness_pb2 as th_pb
import generate_gtest_metadata
import gtest_unittest_const as gtc
import jsonschema
import yaml


class Generate_Gtest_Metadata_Test(TestCase):
    """Main test class for these unit tests"""

    @classmethod
    def setUpClass(cls) -> None:
        """Setup our YAML/parse json as it only needs to be done once"""
        Yaml_Proto = collections.namedtuple("Yaml_Proto", ["yaml", "proto"])
        cls._yaml_proto_data = [
            Yaml_Proto(
                gtc.VALID_YAML_SINGLE_CASE_NO_TAG,
                gtc.VALID_YAML_SINGLE_CASE_NO_TAG_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_SINGLE_CASE_ONE_TAG,
                gtc.VALID_YAML_SINGLE_CASE_ONE_TAG_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_SINGLE_CASE_MULTIPLE_TAGS,
                gtc.VALID_YAML_SINGLE_CASE_MULTIPLE_TAGS_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_MULTIPLE_CASE_NO_TAG,
                gtc.VALID_YAML_MULTIPLE_CASE_NO_TAG_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_MULTIPLE_CASE_ONE_TAG,
                gtc.VALID_YAML_MULTIPLE_CASE_ONE_TAG_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_MULTIPLE_CASE_MULTIPLE_TAGS,
                gtc.VALID_YAML_MULTIPLE_CASE_MULTIPLE_TAGS_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_EMPTY_TEST_BED_DEPS,
                gtc.VALID_YAML_EMPTY_TEST_BED_DEPS_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_SINGLE_TEST_BED_DEPS,
                gtc.VALID_YAML_SINGLE_TEST_BED_DEPS_PROTOBUF,
            ),
            Yaml_Proto(
                gtc.VALID_YAML_MULTIPLE_TEST_BED_DEPS,
                gtc.VALID_YAML_MULTIPLE_TEST_BED_DEPS_PROTOBUF,
            ),
        ]

        with open("gtest_schema.yaml", "r", encoding='utf-8') as f:
            cls._yaml_schema = f.read()

        Bad_Yaml = collections.namedtuple("Bad_Yaml", ["yaml", "msg"])
        cls._bad_yaml_data = [
            Bad_Yaml(
                gtc.INVALID_YAML_NO_AUTHOR,
                'Expected a failure, no "author" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_NAME,
                'Expected a failure, no "name" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_HARNESS,
                'Expected a failure, no "harness" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CATEGORY,
                'Expected a failure, no "category" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_OWNERS,
                'Expected a failure, no "owners" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_EMAIL,
                'Expected a failure, no "owners/email" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CASES,
                'Expected a failure, no "cases" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CASE_ID,
                'Expected a failure, no "cases/id" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CASE_TAGS,
                'Expected a failure, no "cases/tags" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CASE_CRITERIA,
                'Expected a failure, no "cases/criteria" field in yaml!',
            ),
            Bad_Yaml(
                gtc.INVALID_YAML_NO_CASE_TARGET_LOC,
                'Expected a failure, no "cases/target_bin_location" field in yaml!',
            ),
        ]

    def _get_protobuf_bytes(
        self,
        input_files: mock.MagicMock,
        schema_file: mock.MagicMock,
        output_file: mock.MagicMock,
    ) -> bytearray:
        generate_gtest_metadata.main(
            input_files=input_files,
            output_file=output_file,
            yaml_schema_file=schema_file,
        )
        return output_file.write_bytes.call_args[0][0]

    def test_single_file_protobuf_generation(self) -> None:
        """Test that the protobuf generated bytes match expected for a given file"""
        for yp in self._yaml_proto_data:
            schema_file = mock.MagicMock()
            schema_file.read_text.return_value = self._yaml_schema

            input_file = mock.MagicMock()
            input_file.read_text.return_value = yp.yaml

            output_file = mock.MagicMock()

            bytes_from_main = self._get_protobuf_bytes(
                [input_file], schema_file, output_file
            )

            self.assertEqual(yp.proto, bytes_from_main)

    def test_multi_file_protobuf_generation(self) -> None:
        """Test that protobuf generated bytes match expected for a given file"""
        schema_file = mock.MagicMock()
        schema_file.read_text.return_value = self._yaml_schema
        input_files = []
        for yp in self._yaml_proto_data:
            input_file = mock.MagicMock()
            input_file.read_text.return_value = yp.yaml
            input_files.append(input_file)
        output_file = mock.MagicMock()

        bytes_from_main = self._get_protobuf_bytes(
            input_files, schema_file, output_file
        )
        self.assertEqual(gtc.VALID_YAML_ALL_FILES_PROTOBUF, bytes_from_main)

    def test_invalid_yaml(self) -> None:
        """Test yaml schema validation"""
        for ym in self._bad_yaml_data:
            schema_file = mock.MagicMock()
            schema_file.read_text.return_value = self._yaml_schema

            input_file = mock.MagicMock()
            input_file.read_text.return_value = ym.yaml

            output_file = mock.MagicMock()

            with self.assertRaises(
                jsonschema.exceptions.ValidationError, msg=ym.msg
            ):
                self._get_protobuf_bytes([input_file], schema_file, output_file)

    def _build_testcase_metadata_objects(
        self, input_data: list
    ) -> tc_metadata_pb.TestCaseMetadataList:
        cases = []
        for f in input_data:
            s_name = f["name"]

            tce = tc_metadata_pb.TestCaseExec(
                test_harness=th_pb.TestHarness(
                    gtest=th_pb.TestHarness.Gtest(
                        target_bin_location=f["target_bin_location"]
                    )
                )
            )
            tci = tc_metadata_pb.TestCaseInfo(
                owners=[
                    tc_metadata_pb.Contact(email=x["email"])
                    for x in f["owners"]
                ],
                criteria=tc_metadata_pb.Criteria(value=f["criteria"]),
                hw_agnostic=tc_metadata_pb.HwAgnostic(
                    value=f.get("hw_agnostic", False)
                ),
                bug_component=tc_metadata_pb.BugComponent(
                    value=f.get("bug_component", "")
                ),
                requirements=[
                    tc_metadata_pb.Requirement(value=x)
                    for x in f.get("requirements", [])
                ],
            )

            for c in f["cases"]:
                tags = [tc_pb.TestCase.Tag(value=t) for t in c["tags"]]
                tc_id = tc_pb.TestCase.Id(value=f'gtest.{s_name}.{c["id"]}')
                c_name = f'{s_name}.{c["id"]}'
                deps = [
                    tc_pb.TestCase.Dependency(value=t)
                    for t in c.get("testBedDependencies", [])
                ]
                case = tc_pb.TestCase(
                    id=tc_id, name=c_name, tags=tags, dependencies=deps
                )
                cases.append(
                    tc_metadata_pb.TestCaseMetadata(
                        test_case=case, test_case_exec=tce, test_case_info=tci
                    )
                )

        return tc_metadata_pb.TestCaseMetadataList(values=cases)

    def test_proto_objects_single_file(self) -> None:
        """Test proto object building prior to serialization"""
        input_yaml = yaml.safe_load(gtc.VALID_YAML_MULTIPLE_CASE_MULTIPLE_TAGS)

        actual_test_case_list = generate_gtest_metadata._test_case_list_factory(
            input_data=input_yaml
        )
        actual_testcase_metadata_list = tc_metadata_pb.TestCaseMetadataList(
            values=actual_test_case_list
        )

        # Make sure we got our 3 cases
        self.assertEqual(
            len(input_yaml["cases"]), len(actual_testcase_metadata_list.values)
        )

        # Check the object values to make sure they match
        for i, tc in enumerate(actual_testcase_metadata_list.values):
            # Check test harness
            self.assertIsInstance(
                tc.test_case_exec.test_harness.gtest, th_pb.TestHarness.Gtest
            )

            # Check owner/email
            actual_owner_emails = [c.email for c in tc.test_case_info.owners]
            expected_owner_emails = [e["email"] for e in input_yaml["owners"]]
            self.assertListEqual(expected_owner_emails, actual_owner_emails)

            # Check case tags, id, name
            actual_tags = [t.value for t in tc.test_case.tags]
            expected_tags = [t for t in input_yaml["cases"][i]["tags"]]
            self.assertListEqual(expected_tags, actual_tags)

            actual_id = tc.test_case.id.value
            expected_id = (
                f'gtest.{input_yaml["name"]}.{input_yaml["cases"][i]["id"]}'
            )
            self.assertEqual(expected_id, actual_id)

            actual_name = tc.test_case.name
            expected_name = (
                f'{input_yaml["name"]}.{input_yaml["cases"][i]["id"]}'
            )
            self.assertEqual(expected_name, actual_name)

        # Check it all for good measure
        expected_testcase_metadata_list = self._build_testcase_metadata_objects(
            [input_yaml]
        )
        self.assertEqual(
            expected_testcase_metadata_list, actual_testcase_metadata_list
        )

    def test_proto_objects_multiple_file(self) -> None:
        """Test multiple proto object building prior to serialization"""
        input_yaml = [yaml.safe_load(x.yaml) for x in self._yaml_proto_data]

        actual_test_case_list = []
        for y in input_yaml:
            actual_test_case_list.extend(
                generate_gtest_metadata._test_case_list_factory(input_data=y)
            )

        actual_testcase_metadata_list = tc_metadata_pb.TestCaseMetadataList(
            values=actual_test_case_list
        )

        # Check it all for good measure
        expected_testcase_metadata_list = self._build_testcase_metadata_objects(
            input_yaml
        )
        self.assertEqual(
            expected_testcase_metadata_list, actual_testcase_metadata_list
        )


if __name__ == "__main__":
    main(verbosity=2)
