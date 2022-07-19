#!/usr/bin/env python3

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Ignore indention messages, since legacy scripts use 2 spaces instead of 4.
# pylint: disable=bad-indentation,docstring-section-indent
# pylint: disable=docstring-trailing-quotes
# pylint: disable=line-too-long

"""Generate gtest metadata for testexecserv from provided yaml"""

import argparse
import pathlib
import sys

from chromiumos.test.api import test_case_metadata_pb2 as tc_metadata_pb
from chromiumos.test.api import test_case_pb2 as tc_pb
from chromiumos.test.api import test_harness_pb2 as th_pb
from google.protobuf import text_format
import jsonschema
import six
import yaml


def _test_case_exec_factory(target_bin_location: str) -> th_pb.TestHarness:
    """Factory method to build TestCaseExec proto objects

    Args:
        target_bin_location: String representing the path on the DUT to the
                             compiled gtest binary.
    """
    return tc_metadata_pb.TestCaseExec(test_harness=th_pb.TestHarness(
        gtest=th_pb.TestHarness.Gtest(target_bin_location=target_bin_location)))


def _test_case_info_factory(data: dict) -> list:
    """Factory method to build TestCaseInfo proto objects

    Args:
        data: dict representing the 'owners' yaml data
    """
    return tc_metadata_pb.TestCaseInfo(
        owners=[tc_metadata_pb.Contact(email=x['email']) for x in data])


def _test_case_factory(case_data: dict, suite_name: str) -> tc_pb.TestCase:
    """Factory method for build TestCase proto objects

    Args:
        case_data: dict representing the 'cases' yaml data
        suite_name: string representing the 'name' yaml field
    """
    tags = [tc_pb.TestCase.Tag(value=t) for t in case_data['tags']]
    tc_id = tc_pb.TestCase.Id(value=f'gtest.{suite_name}.{case_data["id"]}')
    name = f'{suite_name}.{case_data["id"]}'
    testBedDeps = [tc_pb.TestCase.Dependency(value=t) for t in case_data.get('testBedDependencies', [])]
    return tc_pb.TestCase(id=tc_id, name=name, tags=tags, dependencies=testBedDeps)


def _test_case_metadata_factory(
        case: tc_pb.TestCase, case_exec: tc_metadata_pb.TestCaseExec,
        case_info: tc_metadata_pb.TestCaseInfo
) -> tc_metadata_pb.TestCaseMetadata:
    """Factory method for building TestCaseMetadata proto objects"""
    return tc_metadata_pb.TestCaseMetadata(test_case=case,
                                           test_case_exec=case_exec,
                                           test_case_info=case_info)


def _test_case_list_factory(input_data: dict) -> list:
    """Factory method for batch building TestCaseMetadata objects"""
    suite_name = input_data['name']
    test_case_exec = _test_case_exec_factory(input_data['target_bin_location'])
    test_case_info = _test_case_info_factory(input_data['owners'])

    test_cases = [
        _test_case_factory(tc, suite_name) for tc in input_data['cases']
    ]

    test_case_metadata = [
        _test_case_metadata_factory(case, test_case_exec, test_case_info)
        for case in test_cases
    ]

    return test_case_metadata


def _validate_yaml_file(parsed_yaml: dict, schema: dict):
    """Validate the gtest yaml file against the schema

    The validate() method will throw an exception if the yaml is not valid.

    Args:
        parsed_yaml: dict representation of the yaml file
        schema: dict representation of the yaml schema
    """
    jsonschema.validate(instance=parsed_yaml, schema=schema)


def main(input_files: list, output_file: pathlib.Path,
         yaml_schema_file: pathlib.Path):
    """Main entry point

    Args:
        input_files: list of pathlib.Path objects for yaml metadata files
        output_file: pathlib.Path object for storing generated proto metadata
        yaml_schema_file: pathlib.Path object representing the YAML schema
    """
    test_case_metadata = []

    schema = yaml.safe_load(yaml_schema_file.read_text())

    for f in input_files:
        yaml_data = yaml.safe_load(f.read_text())
        _validate_yaml_file(yaml_data, schema)
        test_case_metadata.extend(_test_case_list_factory(yaml_data))

    test_case_metadata_list = tc_metadata_pb.TestCaseMetadataList(
        values=test_case_metadata)

    # Make sure the appropriate directory structure is created.
    # Mimic "mkdir -p" here.
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(test_case_metadata_list.SerializeToString())


def _argparse_existing_file_factory(path: str) -> pathlib.Path:
    """Create path objects

    Verify the files specified on the command line against:
        1) The file exists
        2) The file is a file, not a directory or other type

    Args:
        path: path to file specified (str)
    """
    p = pathlib.Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(
            f"The specified file '{path}' does not exist!")

    if not p.is_file():
        raise argparse.ArgumentTypeError(
            f"The specified file '{path}' is not a file!")

    return p


def _argparse_file_factory(path: str) -> pathlib.Path:
    """Factory method that builds a pathlib.Path object"""
    return pathlib.Path(path)


if __name__ == '__main__':
    if six.PY2:
        print('ERROR: Python2 detected, this script only runs with python3!')
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description='Generate Gtest harness test case metadata')
    parser.add_argument('--output_file',
                        help='Output file to write proto metadata',
                        type=_argparse_file_factory,
                        required=True)
    parser.add_argument('--yaml_schema',
                        help='YAML schema file to validate test metadata',
                        type=_argparse_existing_file_factory,
                        required=True)
    parser.add_argument('files',
                        help='Gtest YAML metadata files',
                        metavar='INPUT_YAML',
                        type=_argparse_existing_file_factory,
                        nargs='+')
    parser.add_argument(
        '--dump',
        help='Dump pretty printed protobuf to stdout. For debugging purposes',
        action='store_true',
        default=False,
        required=False)

    parser.add_argument(
        '--dump-bytes',
        help='Dump byte array representation of protobuf to stdout. For debugging purposes',
        action='store_true',
        default=False,
        required=False,
        dest='dumpBytes')
    args = parser.parse_args()
    main(args.files, args.output_file, args.yaml_schema)

    if args.dump:
        metadata_list = tc_metadata_pb.TestCaseMetadataList()
        metadata_list.ParseFromString(args.output_file.read_bytes())
        print(text_format.MessageToString(metadata_list))

    if args.dumpBytes:
        print(args.output_file.read_bytes())
