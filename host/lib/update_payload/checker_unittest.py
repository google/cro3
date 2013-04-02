#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit testing checker.py."""

import array
import collections
import cStringIO
import hashlib
import itertools
import os
import unittest

# Pylint cannot find mox.
# pylint: disable=F0401
import mox

import checker
import common
import payload as update_payload  # avoid name conflicts later.
import test_utils
import update_metadata_pb2


def _OpTypeByName(op_name):
  op_name_to_type = {
      'REPLACE': common.OpType.REPLACE,
      'REPLACE_BZ': common.OpType.REPLACE_BZ,
      'MOVE': common.OpType.MOVE,
      'BSDIFF': common.OpType.BSDIFF,
  }
  return op_name_to_type[op_name]


def _GetPayloadChecker(payload_gen_write_to_file_func, payload_gen_dargs=None,
                       checker_init_dargs=None):
  """Returns a payload checker from a given payload generator."""
  if payload_gen_dargs is None:
    payload_gen_dargs = {}
  if checker_init_dargs is None:
    checker_init_dargs = {}

  payload_file = cStringIO.StringIO()
  payload_gen_write_to_file_func(payload_file, **payload_gen_dargs)
  payload_file.seek(0)
  payload = update_payload.Payload(payload_file)
  payload.Init()
  return checker.PayloadChecker(payload, **checker_init_dargs)


def _GetPayloadCheckerWithData(payload_gen):
  """Returns a payload checker from a given payload generator."""
  payload_file = cStringIO.StringIO()
  payload_gen.WriteToFile(payload_file)
  payload_file.seek(0)
  payload = update_payload.Payload(payload_file)
  payload.Init()
  return checker.PayloadChecker(payload)


# (i) this class doesn't need an __init__();  (ii) unit testing is all about
# running protected methods;  (iii) don't bark about missing members of classes
# you cannot import.
# pylint: disable=W0232
# pylint: disable=W0212
# pylint: disable=E1101
class PayloadCheckerTest(mox.MoxTestBase):
  """Tests the PayloadChecker class.

  In addition to ordinary testFoo() methods, which are automatically invoked by
  the unittest framework, in this class we make use of DoBarTest() calls that
  implement parametric tests of certain features. In order to invoke each test,
  which embodies a unique combination of parameter values, as a complete unit
  test, we perform explicit enumeration of the parameter space and create
  individual invocation contexts for each, which are then bound as
  testBar__param1=val1__param2=val2(). The enumeration of parameter spaces for
  all such tests is done in AddAllParametricTests().

  """

  def MockPayload(self):
    """Create a mock payload object, complete with a mock menifest."""
    payload = self.mox.CreateMock(update_payload.Payload)
    payload.is_init = True
    payload.manifest = self.mox.CreateMock(
        update_metadata_pb2.DeltaArchiveManifest)
    return payload

  @staticmethod
  def NewExtent(start_block, num_blocks):
    """Returns an Extent message.

    Each of the provided fields is set iff it is >= 0; otherwise, it's left at
    its default state.

    Args:
      start_block: the starting block of the extent
      num_blocks: the number of blocks in the extent
    Returns:
      An Extent message.

    """
    ex = update_metadata_pb2.Extent()
    if start_block >= 0:
      ex.start_block = start_block
    if num_blocks >= 0:
      ex.num_blocks = num_blocks
    return ex

  @staticmethod
  def NewExtentList(*args):
    """Returns an list of extents.

    Args:
      *args: (start_block, num_blocks) pairs defining the extents
    Returns:
      A list of Extent objects.

    """
    ex_list = []
    for start_block, num_blocks in args:
      ex_list.append(PayloadCheckerTest.NewExtent(start_block, num_blocks))
    return ex_list

  @staticmethod
  def AddToMessage(repeated_field, field_vals):
    for field_val in field_vals:
      new_field = repeated_field.add()
      new_field.CopyFrom(field_val)

  def assertIsNone(self, val):
    """Asserts that val is None (TODO remove once we upgrade to Python 2.7).

    Note that we're using assertEqual so as for it to show us the actual
    non-None value.

    Args:
      val: value/object to be equated to None

    """
    self.assertEqual(val, None)

  def SetupAddElemTest(self, is_present, is_submsg, convert=str,
                       linebreak=False, indent=0):
    """Setup for testing of _CheckElem() and its derivatives.

    Args:
      is_present: whether or not the element is found in the message
      is_submsg: whether the element is a sub-message itself
      convert: a representation conversion function
      linebreak: whether or not a linebreak is to be used in the report
      indent: indentation used for the report
    Returns:
      msg: a mock message object
      report: a mock report object
      subreport: a mock sub-report object
      name: an element name to check
      val: expected element value

    """
    name = 'foo'
    val = 'fake submsg' if is_submsg else 'fake field'
    subreport = 'fake subreport'

    # Create a mock message.
    msg = self.mox.CreateMock(update_metadata_pb2.message.Message)
    msg.HasField(name).AndReturn(is_present)
    setattr(msg, name, val)

    # Create a mock report.
    report = self.mox.CreateMock(checker._PayloadReport)
    if is_present:
      if is_submsg:
        report.AddSubReport(name).AndReturn(subreport)
      else:
        report.AddField(name, convert(val), linebreak=linebreak, indent=indent)

    self.mox.ReplayAll()
    return (msg, report, subreport, name, val)

  def DoAddElemTest(self, is_present, is_mandatory, is_submsg, convert,
                    linebreak, indent):
    """Parametric testing of _CheckElem().

    Args:
      is_present: whether or not the element is found in the message
      is_mandatory: whether or not it's a mandatory element
      is_submsg: whether the element is a sub-message itself
      convert: a representation conversion function
      linebreak: whether or not a linebreak is to be used in the report
      indent: indentation used for the report

    """
    msg, report, subreport, name, val = self.SetupAddElemTest(
        is_present, is_submsg, convert, linebreak, indent)

    largs = [msg, name, report, is_mandatory, is_submsg]
    dargs = {'convert': convert, 'linebreak': linebreak, 'indent': indent}
    if is_mandatory and not is_present:
      self.assertRaises(update_payload.PayloadError,
                        checker.PayloadChecker._CheckElem, *largs, **dargs)
    else:
      ret_val, ret_subreport = checker.PayloadChecker._CheckElem(*largs,
                                                                 **dargs)
      self.assertEquals(ret_val, val if is_present else None)
      self.assertEquals(ret_subreport,
                        subreport if is_present and is_submsg else None)

  def DoAddFieldTest(self, is_mandatory, is_present, convert, linebreak,
                     indent):
    """Parametric testing of _Check{Mandatory,Optional}Field().

    Args:
      is_mandatory: whether we're testing a mandatory call
      is_present: whether or not the element is found in the message
      convert: a representation conversion function
      linebreak: whether or not a linebreak is to be used in the report
      indent: indentation used for the report

    """
    msg, report, _, name, val = self.SetupAddElemTest(
        is_present, False, convert, linebreak, indent)

    # Prepare for invocation of the tested method.
    largs = [msg, name, report]
    dargs = {'convert': convert, 'linebreak': linebreak, 'indent': indent}
    if is_mandatory:
      largs.append('bar')
      tested_func = checker.PayloadChecker._CheckMandatoryField
    else:
      tested_func = checker.PayloadChecker._CheckOptionalField

    # Test the method call.
    if is_mandatory and not is_present:
      self.assertRaises(update_payload.PayloadError, tested_func, *largs,
                        **dargs)
    else:
      ret_val = tested_func(*largs, **dargs)
      self.assertEquals(ret_val, val if is_present else None)

  def DoAddSubMsgTest(self, is_mandatory, is_present):
    """Parametrized testing of _Check{Mandatory,Optional}SubMsg().

    Args:
      is_mandatory: whether we're testing a mandatory call
      is_present: whether or not the element is found in the message

    """
    msg, report, subreport, name, val = self.SetupAddElemTest(is_present, True)

    # Prepare for invocation of the tested method.
    largs = [msg, name, report]
    if is_mandatory:
      largs.append('bar')
      tested_func = checker.PayloadChecker._CheckMandatorySubMsg
    else:
      tested_func = checker.PayloadChecker._CheckOptionalSubMsg

    # Test the method call.
    if is_mandatory and not is_present:
      self.assertRaises(update_payload.PayloadError, tested_func, *largs)
    else:
      ret_val, ret_subreport = tested_func(*largs)
      self.assertEquals(ret_val, val if is_present else None)
      self.assertEquals(ret_subreport, subreport if is_present else None)

  def testCheckPresentIff(self):
    """Tests _CheckPresentIff()."""
    self.assertIsNone(checker.PayloadChecker._CheckPresentIff(
        None, None, 'foo', 'bar', 'baz'))
    self.assertIsNone(checker.PayloadChecker._CheckPresentIff(
        'a', 'b', 'foo', 'bar', 'baz'))
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckPresentIff,
                      'a', None, 'foo', 'bar', 'baz')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckPresentIff,
                      None, 'b', 'foo', 'bar', 'baz')

  def DoCheckSha256SignatureTest(self, expect_pass, expect_subprocess_call,
                                 sig_data, sig_asn1_header,
                                 returned_signed_hash, expected_signed_hash):
    """Parametric testing of _CheckSha256SignatureTest().

    Args:
      expect_pass: whether or not it should pass
      expect_subprocess_call: whether to expect the openssl call to happen
      sig_data: the signature raw data
      sig_asn1_header: the ASN1 header
      returned_signed_hash: the signed hash data retuned by openssl
      expected_signed_hash: the signed hash data to compare against

    """
    # Stub out the subprocess invocation.
    self.mox.StubOutWithMock(checker.PayloadChecker, '_Run')
    if expect_subprocess_call:
      checker.PayloadChecker._Run(mox.IsA(list), send_data=sig_data).AndReturn(
          (sig_asn1_header + returned_signed_hash, None))

    self.mox.ReplayAll()
    if expect_pass:
      self.assertIsNone(checker.PayloadChecker._CheckSha256Signature(
          sig_data, 'foo', expected_signed_hash, 'bar'))
    else:
      self.assertRaises(update_payload.PayloadError,
                        checker.PayloadChecker._CheckSha256Signature,
                        sig_data, 'foo', expected_signed_hash, 'bar')

    self.mox.UnsetStubs()

  def testCheckSha256Signature_Pass(self):
    """Tests _CheckSha256Signature(); pass case."""
    sig_data = 'fake-signature'.ljust(256)
    signed_hash = hashlib.sha256('fake-data').digest()
    self.DoCheckSha256SignatureTest(True, True, sig_data,
                                    common.SIG_ASN1_HEADER, signed_hash,
                                    signed_hash)

  def testCheckSha256Signature_FailBadSignature(self):
    """Tests _CheckSha256Signature(); fails due to malformed signature."""
    sig_data = 'fake-signature'  # malformed (not 256 bytes in length)
    signed_hash = hashlib.sha256('fake-data').digest()
    self.DoCheckSha256SignatureTest(False, False, sig_data,
                                    common.SIG_ASN1_HEADER, signed_hash,
                                    signed_hash)

  def testCheckSha256Signature_FailBadOutputLength(self):
    """Tests _CheckSha256Signature(); fails due to unexpected output length."""
    sig_data = 'fake-signature'.ljust(256)
    signed_hash = 'fake-hash'  # malformed (not 32 bytes in length)
    self.DoCheckSha256SignatureTest(False, True, sig_data,
                                    common.SIG_ASN1_HEADER, signed_hash,
                                    signed_hash)

  def testCheckSha256Signature_FailBadAsnHeader(self):
    """Tests _CheckSha256Signature(); fails due to bad ASN1 header."""
    sig_data = 'fake-signature'.ljust(256)
    signed_hash = hashlib.sha256('fake-data').digest()
    bad_asn1_header = 'bad-asn-header'.ljust(len(common.SIG_ASN1_HEADER))
    self.DoCheckSha256SignatureTest(False, True, sig_data, bad_asn1_header,
                                    signed_hash, signed_hash)

  def testCheckSha256Signature_FailBadHash(self):
    """Tests _CheckSha256Signature(); fails due to bad hash returned."""
    sig_data = 'fake-signature'.ljust(256)
    expected_signed_hash = hashlib.sha256('fake-data').digest()
    returned_signed_hash = hashlib.sha256('bad-fake-data').digest()
    self.DoCheckSha256SignatureTest(False, True, sig_data,
                                    common.SIG_ASN1_HEADER,
                                    expected_signed_hash, returned_signed_hash)

  def testCheckBlocksFitLength_Pass(self):
    """Tests _CheckBlocksFitLength(); pass case."""
    self.assertIsNone(checker.PayloadChecker._CheckBlocksFitLength(
        64, 4, 16, 'foo'))
    self.assertIsNone(checker.PayloadChecker._CheckBlocksFitLength(
        60, 4, 16, 'foo'))
    self.assertIsNone(checker.PayloadChecker._CheckBlocksFitLength(
        49, 4, 16, 'foo'))
    self.assertIsNone(checker.PayloadChecker._CheckBlocksFitLength(
        48, 3, 16, 'foo'))

  def testCheckBlocksFitLength_TooManyBlocks(self):
    """Tests _CheckBlocksFitLength(); fails due to excess blocks."""
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      64, 5, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      60, 5, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      49, 5, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      48, 4, 16, 'foo')

  def testCheckBlocksFitLength_TooFewBlocks(self):
    """Tests _CheckBlocksFitLength(); fails due to insufficient blocks."""
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      64, 3, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      60, 3, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      49, 3, 16, 'foo')
    self.assertRaises(update_payload.PayloadError,
                      checker.PayloadChecker._CheckBlocksFitLength,
                      48, 2, 16, 'foo')

  def DoCheckManifestTest(self, fail_mismatched_block_size, fail_bad_sigs,
                          fail_mismatched_oki_ori, fail_bad_oki, fail_bad_ori,
                          fail_bad_nki, fail_bad_nri, fail_missing_ops,
                          fail_old_kernel_fs_size, fail_old_rootfs_fs_size,
                          fail_new_kernel_fs_size, fail_new_rootfs_fs_size):
    """Parametric testing of _CheckManifest().

    Args:
      fail_mismatched_block_size: simulate a missing block_size field
      fail_bad_sigs: make signatures descriptor inconsistent
      fail_mismatched_oki_ori: make old rootfs/kernel info partially present
      fail_bad_oki: tamper with old kernel info
      fail_bad_ori: tamper with old rootfs info
      fail_bad_nki: tamper with new kernel info
      fail_bad_nri: tamper with new rootfs info
      fail_missing_ops: simulate a manifest without any operations
      fail_old_kernel_fs_size: make old kernel fs size too big
      fail_old_rootfs_fs_size: make old rootfs fs size too big
      fail_new_kernel_fs_size: make new kernel fs size too big
      fail_new_rootfs_fs_size: make new rootfs fs size too big

    """
    # Generate a test payload. For this test, we only care about the manifest
    # and don't need any data blobs, hence we can use a plain paylaod generator
    # (which also gives us more control on things that can be screwed up).
    payload_gen = test_utils.PayloadGenerator()

    # Tamper with block size, if required.
    if fail_mismatched_block_size:
      payload_gen.SetBlockSize(test_utils.KiB(1))
    else:
      payload_gen.SetBlockSize(test_utils.KiB(4))

    # Add some operations.
    if not fail_missing_ops:
      payload_gen.AddOperation(False, common.OpType.MOVE,
                               src_extents=[(0, 16), (16, 497)],
                               dst_extents=[(16, 496), (0, 16)])
      payload_gen.AddOperation(True, common.OpType.MOVE,
                               src_extents=[(0, 8), (8, 8)],
                               dst_extents=[(8, 8), (0, 8)])

    # Set an invalid signatures block (offset but no size), if required.
    if fail_bad_sigs:
      payload_gen.SetSignatures(32, None)

    # Set partition / filesystem sizes.
    rootfs_part_size = test_utils.MiB(8)
    kernel_part_size = test_utils.KiB(512)
    old_rootfs_fs_size = new_rootfs_fs_size = rootfs_part_size
    old_kernel_fs_size = new_kernel_fs_size = kernel_part_size
    if fail_old_kernel_fs_size:
      old_kernel_fs_size += 100
    if fail_old_rootfs_fs_size:
      old_rootfs_fs_size += 100
    if fail_new_kernel_fs_size:
      new_kernel_fs_size += 100
    if fail_new_rootfs_fs_size:
      new_rootfs_fs_size += 100

    # Add old kernel/rootfs partition info, as required.
    if fail_mismatched_oki_ori or fail_old_kernel_fs_size or fail_bad_oki:
      oki_hash = (None if fail_bad_oki
                  else hashlib.sha256('fake-oki-content').digest())
      payload_gen.SetPartInfo(True, False, old_kernel_fs_size, oki_hash)
    if not fail_mismatched_oki_ori and (fail_old_rootfs_fs_size or
                                        fail_bad_ori):
      ori_hash = (None if fail_bad_ori
                  else hashlib.sha256('fake-ori-content').digest())
      payload_gen.SetPartInfo(False, False, old_rootfs_fs_size, ori_hash)

    # Add new kernel/rootfs partition info.
    payload_gen.SetPartInfo(
        True, True, new_kernel_fs_size,
        None if fail_bad_nki else hashlib.sha256('fake-nki-content').digest())
    payload_gen.SetPartInfo(
        False, True, new_rootfs_fs_size,
        None if fail_bad_nri else hashlib.sha256('fake-nri-content').digest())

    # Create the test object.
    payload_checker = _GetPayloadChecker(payload_gen.WriteToFile)
    report = checker._PayloadReport()

    should_fail = (fail_mismatched_block_size or fail_bad_sigs or
                   fail_mismatched_oki_ori or fail_bad_oki or fail_bad_ori or
                   fail_bad_nki or fail_bad_nri or fail_missing_ops or
                   fail_old_kernel_fs_size or fail_old_rootfs_fs_size or
                   fail_new_kernel_fs_size or fail_new_rootfs_fs_size)
    if should_fail:
      self.assertRaises(update_payload.PayloadError,
                        payload_checker._CheckManifest, report,
                        rootfs_part_size, kernel_part_size)
    else:
      self.assertIsNone(payload_checker._CheckManifest(report,
                                                       rootfs_part_size,
                                                       kernel_part_size))

  def testCheckLength(self):
    """Tests _CheckLength()."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    block_size = payload_checker.block_size

    # Passes.
    self.assertIsNone(payload_checker._CheckLength(
        int(3.5 * block_size), 4, 'foo', 'bar'))
    # Fails, too few blocks.
    self.assertRaises(update_payload.PayloadError,
                      payload_checker._CheckLength,
                      int(3.5 * block_size), 3, 'foo', 'bar')
    # Fails, too many blocks.
    self.assertRaises(update_payload.PayloadError,
                      payload_checker._CheckLength,
                      int(3.5 * block_size), 5, 'foo', 'bar')

  def testCheckExtents(self):
    """Tests _CheckExtents()."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    block_size = payload_checker.block_size

    # Passes w/ all real extents.
    extents = self.NewExtentList((0, 4), (8, 3), (1024, 16))
    self.assertEquals(
        payload_checker._CheckExtents(extents, (1024 + 16) * block_size,
                                      collections.defaultdict(int), 'foo'),
        23)

    # Passes w/ pseudo-extents (aka sparse holes).
    extents = self.NewExtentList((0, 4), (common.PSEUDO_EXTENT_MARKER, 5),
                                 (8, 3))
    self.assertEquals(
        payload_checker._CheckExtents(extents, (1024 + 16) * block_size,
                                      collections.defaultdict(int), 'foo',
                                      allow_pseudo=True),
        12)

    # Passes w/ pseudo-extent due to a signature.
    extents = self.NewExtentList((common.PSEUDO_EXTENT_MARKER, 2))
    self.assertEquals(
        payload_checker._CheckExtents(extents, (1024 + 16) * block_size,
                                      collections.defaultdict(int), 'foo',
                                      allow_signature=True),
        2)

    # Fails, extent missing a start block.
    extents = self.NewExtentList((-1, 4), (8, 3), (1024, 16))
    self.assertRaises(
        update_payload.PayloadError, payload_checker._CheckExtents,
        extents, (1024 + 16) * block_size, collections.defaultdict(int),
        'foo')

    # Fails, extent missing block count.
    extents = self.NewExtentList((0, -1), (8, 3), (1024, 16))
    self.assertRaises(
        update_payload.PayloadError, payload_checker._CheckExtents,
        extents, (1024 + 16) * block_size, collections.defaultdict(int),
        'foo')

    # Fails, extent has zero blocks.
    extents = self.NewExtentList((0, 4), (8, 3), (1024, 0))
    self.assertRaises(
        update_payload.PayloadError, payload_checker._CheckExtents,
        extents, (1024 + 16) * block_size, collections.defaultdict(int),
        'foo')

    # Fails, extent exceeds partition boundaries.
    extents = self.NewExtentList((0, 4), (8, 3), (1024, 16))
    self.assertRaises(
        update_payload.PayloadError, payload_checker._CheckExtents,
        extents, (1024 + 15) * block_size, collections.defaultdict(int),
        'foo')

  def testCheckReplaceOperation(self):
    """Tests _CheckReplaceOperation() where op.type == REPLACE."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    block_size = payload_checker.block_size
    data_length = 10000

    op = self.mox.CreateMock(
        update_metadata_pb2.DeltaArchiveManifest.InstallOperation)
    op.type = common.OpType.REPLACE

    # Pass.
    op.src_extents = []
    self.assertIsNone(
        payload_checker._CheckReplaceOperation(
            op, data_length, (data_length + block_size - 1) / block_size,
            'foo'))

    # Fail, src extents founds.
    op.src_extents = ['bar']
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, data_length, (data_length + block_size - 1) / block_size, 'foo')

    # Fail, missing data.
    op.src_extents = []
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, None, (data_length + block_size - 1) / block_size, 'foo')

    # Fail, length / block number mismatch.
    op.src_extents = ['bar']
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, data_length, (data_length + block_size - 1) / block_size + 1, 'foo')

  def testCheckReplaceBzOperation(self):
    """Tests _CheckReplaceOperation() where op.type == REPLACE_BZ."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    block_size = payload_checker.block_size
    data_length = block_size * 3

    op = self.mox.CreateMock(
        update_metadata_pb2.DeltaArchiveManifest.InstallOperation)
    op.type = common.OpType.REPLACE_BZ

    # Pass.
    op.src_extents = []
    self.assertIsNone(
        payload_checker._CheckReplaceOperation(
            op, data_length, (data_length + block_size - 1) / block_size + 5,
            'foo'))

    # Fail, src extents founds.
    op.src_extents = ['bar']
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, data_length, (data_length + block_size - 1) / block_size + 5, 'foo')

    # Fail, missing data.
    op.src_extents = []
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, None, (data_length + block_size - 1) / block_size, 'foo')

    # Fail, too few blocks to justify BZ.
    op.src_extents = []
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckReplaceOperation,
        op, data_length, (data_length + block_size - 1) / block_size, 'foo')

  def testCheckMoveOperation_Pass(self):
    """Tests _CheckMoveOperation(); pass case."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 6)))
    self.assertIsNone(
        payload_checker._CheckMoveOperation(op, None, 134, 134, 'foo'))

  def testCheckMoveOperation_FailContainsData(self):
    """Tests _CheckMoveOperation(); fails, message contains data."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 6)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, 1024, 134, 134, 'foo')

  def testCheckMoveOperation_FailInsufficientSrcBlocks(self):
    """Tests _CheckMoveOperation(); fails, not enough actual src blocks."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 127)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 6)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')

  def testCheckMoveOperation_FailInsufficientDstBlocks(self):
    """Tests _CheckMoveOperation(); fails, not enough actual dst blocks."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 5)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')

  def testCheckMoveOperation_FailExcessSrcBlocks(self):
    """Tests _CheckMoveOperation(); fails, too many actual src blocks."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 5)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')
    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 129)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 6)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')

  def testCheckMoveOperation_FailExcessDstBlocks(self):
    """Tests _CheckMoveOperation(); fails, too many actual dst blocks."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((16, 128), (512, 7)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')

  def testCheckMoveOperation_FailStagnantBlocks(self):
    """Tests _CheckMoveOperation(); fails, there are blocks that do not move."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = common.OpType.MOVE

    self.AddToMessage(op.src_extents,
                      self.NewExtentList((0, 4), (12, 2), (1024, 128)))
    self.AddToMessage(op.dst_extents,
                      self.NewExtentList((8, 128), (512, 6)))
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckMoveOperation,
        op, None, 134, 134, 'foo')

  def testCheckBsdiff(self):
    """Tests _CheckMoveOperation()."""
    payload_checker = checker.PayloadChecker(self.MockPayload())

    # Pass.
    self.assertIsNone(
        payload_checker._CheckBsdiffOperation(10000, 3, 'foo'))

    # Fail, missing data blob.
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckBsdiffOperation,
        None, 3, 'foo')

    # Fail, too big of a diff blob (unjustified).
    self.assertRaises(
        update_payload.PayloadError,
        payload_checker._CheckBsdiffOperation,
        10000, 2, 'foo')

  def DoCheckOperationTest(self, op_type_name, is_last, allow_signature,
                           allow_unhashed, fail_src_extents, fail_dst_extents,
                           fail_mismatched_data_offset_length,
                           fail_missing_dst_extents, fail_src_length,
                           fail_dst_length, fail_data_hash,
                           fail_prev_data_offset):
    """Parametric testing of _CheckOperation().

    Args:
      op_type_name: 'REPLACE', 'REPLACE_BZ', 'MOVE' or 'BSDIFF'
      is_last: whether we're testing the last operation in a sequence
      allow_signature: whether we're testing a signature-capable operation
      allow_unhashed: whether we're allowing to not hash the data
      fail_src_extents: tamper with src extents
      fail_dst_extents: tamper with dst extents
      fail_mismatched_data_offset_length: make data_{offset,length} inconsistent
      fail_missing_dst_extents: do not include dst extents
      fail_src_length: make src length inconsistent
      fail_dst_length: make dst length inconsistent
      fail_data_hash: tamper with the data blob hash
      fail_prev_data_offset: make data space uses incontiguous

    """
    op_type = _OpTypeByName(op_type_name)

    # Create the test object.
    payload = self.MockPayload()
    payload_checker = checker.PayloadChecker(payload,
                                             allow_unhashed=allow_unhashed)
    block_size = payload_checker.block_size

    # Create auxiliary arguments.
    old_part_size = test_utils.MiB(4)
    new_part_size = test_utils.MiB(8)
    old_block_counters = array.array(
        'B', [0] * ((old_part_size + block_size - 1) / block_size))
    new_block_counters = array.array(
        'B', [0] * ((new_part_size + block_size - 1) / block_size))
    prev_data_offset = 1876
    blob_hash_counts = collections.defaultdict(int)

    # Create the operation object for the test.
    op = update_metadata_pb2.DeltaArchiveManifest.InstallOperation()
    op.type = op_type

    total_src_blocks = 0
    if op_type in (common.OpType.MOVE, common.OpType.BSDIFF):
      if fail_src_extents:
        self.AddToMessage(op.src_extents,
                          self.NewExtentList((0, 0)))
      else:
        self.AddToMessage(op.src_extents,
                          self.NewExtentList((0, 16)))
        total_src_blocks = 16

    if op_type != common.OpType.MOVE:
      if not fail_mismatched_data_offset_length:
        op.data_length = 16 * block_size - 8
      if fail_prev_data_offset:
        op.data_offset = prev_data_offset + 16
      else:
        op.data_offset = prev_data_offset

      fake_data = 'fake-data'.ljust(op.data_length)
      if not (allow_unhashed or (is_last and allow_signature and
                                 op_type == common.OpType.REPLACE)):
        if not fail_data_hash:
          # Create a valid data blob hash.
          op.data_sha256_hash = hashlib.sha256(fake_data).digest()
          payload.ReadDataBlob(op.data_offset, op.data_length).AndReturn(
              fake_data)
      elif fail_data_hash:
        # Create an invalid data blob hash.
        op.data_sha256_hash = hashlib.sha256(
            fake_data.replace(' ', '-')).digest()
        payload.ReadDataBlob(op.data_offset, op.data_length).AndReturn(
            fake_data)

    total_dst_blocks = 0
    if not fail_missing_dst_extents:
      total_dst_blocks = 16
      if fail_dst_extents:
        self.AddToMessage(op.dst_extents,
                          self.NewExtentList((4, 16), (32, 0)))
      else:
        self.AddToMessage(op.dst_extents,
                          self.NewExtentList((4, 8), (64, 8)))

    if total_src_blocks:
      if fail_src_length:
        op.src_length = total_src_blocks * block_size + 8
      else:
        op.src_length = total_src_blocks * block_size
    elif fail_src_length:
      # Add an orphaned src_length.
      op.src_length = 16

    if total_dst_blocks:
      if fail_dst_length:
        op.dst_length = total_dst_blocks * block_size + 8
      else:
        op.dst_length = total_dst_blocks * block_size

    self.mox.ReplayAll()
    should_fail = (fail_src_extents or fail_dst_extents or
                   fail_mismatched_data_offset_length or
                   fail_missing_dst_extents or fail_src_length or
                   fail_dst_length or fail_data_hash or fail_prev_data_offset)
    largs = [op, 'foo', is_last, old_block_counters, new_block_counters,
             old_part_size, new_part_size, prev_data_offset, allow_signature,
             blob_hash_counts]
    if should_fail:
      self.assertRaises(update_payload.PayloadError,
                        payload_checker._CheckOperation, *largs)
    else:
      self.assertEqual(payload_checker._CheckOperation(*largs),
                       op.data_length if op.HasField('data_length') else 0)

  def testAllocBlockCounters(self):
    """Tests _CheckMoveOperation()."""
    payload_checker = checker.PayloadChecker(self.MockPayload())
    block_size = payload_checker.block_size

    # Check allocation for block-aligned partition size, ensure it's integers.
    result = payload_checker._AllocBlockCounters(16 * block_size)
    self.assertEqual(len(result), 16)
    self.assertEqual(type(result[0]), int)

    # Check allocation of unaligned partition sizes.
    result = payload_checker._AllocBlockCounters(16 * block_size - 1)
    self.assertEqual(len(result), 16)
    result = payload_checker._AllocBlockCounters(16 * block_size + 1)
    self.assertEqual(len(result), 17)

  def DoCheckOperationsTest(self, fail_bad_type,
                            fail_nonexhaustive_full_update):
    # Generate a test payload. For this test, we only care about one
    # (arbitrary) set of operations, so we'll only be generating kernel and
    # test with them.
    payload_gen = test_utils.PayloadGenerator()

    block_size = test_utils.KiB(4)
    payload_gen.SetBlockSize(block_size)

    rootfs_part_size = test_utils.MiB(8)

    # Fake rootfs operations in a full update, tampered with as required.
    rootfs_op_type = common.OpType.REPLACE
    if fail_bad_type:
      # Choose a type value that's bigger than the highest valid value.
      for valid_op_type in common.OpType.ALL:
        rootfs_op_type = max(rootfs_op_type, valid_op_type)
      rootfs_op_type += 1

    rootfs_data_length = rootfs_part_size
    if fail_nonexhaustive_full_update:
      rootfs_data_length -= block_size

    payload_gen.AddOperation(False, rootfs_op_type,
                             dst_extents=[(0, rootfs_data_length / block_size)],
                             data_offset=0,
                             data_length=rootfs_data_length)

    # Create the test object.
    payload_checker = _GetPayloadChecker(payload_gen.WriteToFile,
                                         checker_init_dargs={
                                             'allow_unhashed': True})
    payload_checker.payload_type = checker._TYPE_FULL
    report = checker._PayloadReport()

    should_fail = (fail_bad_type or fail_nonexhaustive_full_update)
    largs = (payload_checker.payload.manifest.install_operations, report,
             'foo', 0, rootfs_part_size, rootfs_part_size, 0, False)
    if should_fail:
      self.assertRaises(update_payload.PayloadError,
                        payload_checker._CheckOperations, *largs)
    else:
      self.assertEqual(payload_checker._CheckOperations(*largs),
                       rootfs_data_length)

  def DoCheckSignaturesTest(self, fail_empty_sigs_blob, fail_missing_pseudo_op,
                            fail_mismatched_pseudo_op, fail_sig_missing_fields,
                            fail_unknown_sig_version, fail_incorrect_sig):
    # Generate a test payload. For this test, we only care about the signature
    # block and how it relates to the payload hash. Therefore, we're generating
    # a random (otherwise useless) payload for this purpose.
    payload_gen = test_utils.EnhancedPayloadGenerator()
    block_size = test_utils.KiB(4)
    payload_gen.SetBlockSize(block_size)
    rootfs_part_size = test_utils.MiB(2)
    kernel_part_size = test_utils.KiB(16)
    payload_gen.SetPartInfo(False, True, rootfs_part_size,
                            hashlib.sha256('fake-new-rootfs-content').digest())
    payload_gen.SetPartInfo(True, True, kernel_part_size,
                            hashlib.sha256('fake-new-kernel-content').digest())
    payload_gen.AddOperationWithData(
        False, common.OpType.REPLACE,
        dst_extents=[(0, rootfs_part_size / block_size)],
        data_blob=os.urandom(rootfs_part_size))

    do_forge_pseudo_op = (fail_missing_pseudo_op or fail_mismatched_pseudo_op)
    do_forge_sigs_data = (do_forge_pseudo_op or fail_empty_sigs_blob or
                          fail_sig_missing_fields or fail_unknown_sig_version
                          or fail_incorrect_sig)

    sigs_data = None
    if do_forge_sigs_data:
      sigs_gen = test_utils.SignaturesGenerator()
      if not fail_empty_sigs_blob:
        if fail_sig_missing_fields:
          sig_data = None
        else:
          sig_data = test_utils.SignSha256('fake-payload-content',
                                           test_utils._PRIVKEY_FILE_NAME)
        sigs_gen.AddSig(5 if fail_unknown_sig_version else 1, sig_data)

      sigs_data = sigs_gen.ToBinary()
      payload_gen.SetSignatures(payload_gen.curr_offset, len(sigs_data))

    if do_forge_pseudo_op:
      assert sigs_data is not None, 'should have forged signatures blob by now'
      sigs_len = len(sigs_data)
      payload_gen.AddOperation(
          False, common.OpType.REPLACE,
          data_offset=payload_gen.curr_offset / 2,
          data_length=sigs_len / 2,
          dst_extents=[(0, (sigs_len / 2 + block_size - 1) / block_size)])

    # Generate payload (complete w/ signature) and create the test object.
    payload_checker = _GetPayloadChecker(
        payload_gen.WriteToFileWithData,
        payload_gen_dargs={
            'sigs_data': sigs_data,
            'privkey_file_name': test_utils._PRIVKEY_FILE_NAME,
            'do_add_pseudo_operation': not do_forge_pseudo_op})
    payload_checker.payload_type = checker._TYPE_FULL
    report = checker._PayloadReport()

    # We have to check the manifest first in order to set signature attributes.
    payload_checker._CheckManifest(report, rootfs_part_size, kernel_part_size)

    should_fail = (fail_empty_sigs_blob or fail_missing_pseudo_op or
                   fail_mismatched_pseudo_op or fail_sig_missing_fields or
                   fail_unknown_sig_version or fail_incorrect_sig)
    largs = (report, test_utils._PUBKEY_FILE_NAME)
    if should_fail:
      self.assertRaises(update_payload.PayloadError,
                        payload_checker._CheckSignatures, *largs)
    else:
      self.assertIsNone(payload_checker._CheckSignatures(*largs))

  def DoRunTest(self, fail_wrong_payload_type, fail_invalid_block_size,
                fail_mismatched_block_size, fail_excess_data):
    # Generate a test payload. For this test, we generate a full update that
    # has sample kernel and rootfs operations. Since most testing is done with
    # internal PayloadChecker methods that are tested elsewhere, here we only
    # tamper with what's actually being manipulated and/or tested in the Run()
    # method itself. Note that the checker doesn't verify partition hashes, so
    # they're safe to fake.
    payload_gen = test_utils.EnhancedPayloadGenerator()
    block_size = test_utils.KiB(4)
    payload_gen.SetBlockSize(block_size)
    kernel_part_size = test_utils.KiB(16)
    rootfs_part_size = test_utils.MiB(2)
    payload_gen.SetPartInfo(False, True, rootfs_part_size,
                            hashlib.sha256('fake-new-rootfs-content').digest())
    payload_gen.SetPartInfo(True, True, kernel_part_size,
                            hashlib.sha256('fake-new-kernel-content').digest())
    payload_gen.AddOperationWithData(
        False, common.OpType.REPLACE,
        dst_extents=[(0, rootfs_part_size / block_size)],
        data_blob=os.urandom(rootfs_part_size))
    payload_gen.AddOperationWithData(
        True, common.OpType.REPLACE,
        dst_extents=[(0, kernel_part_size / block_size)],
        data_blob=os.urandom(kernel_part_size))

    # Generate payload (complete w/ signature) and create the test object.
    if fail_invalid_block_size:
      use_block_size = block_size + 5  # not a power of two
    elif fail_mismatched_block_size:
      use_block_size = block_size * 2  # different that payload stated
    else:
      use_block_size = block_size

    dargs = {
        'payload_gen_dargs': {
            'privkey_file_name': test_utils._PRIVKEY_FILE_NAME,
            'do_add_pseudo_operation': True,
            'is_pseudo_in_kernel': True,
            'padding': os.urandom(1024) if fail_excess_data else None},
        'checker_init_dargs': {
            'assert_type': 'delta' if fail_wrong_payload_type else 'full',
            'block_size': use_block_size}}
    if fail_invalid_block_size:
      self.assertRaises(update_payload.PayloadError, _GetPayloadChecker,
                        payload_gen.WriteToFileWithData, **dargs)
    else:
      payload_checker = _GetPayloadChecker(payload_gen.WriteToFileWithData,
                                           **dargs)
      dargs = {'pubkey_file_name': test_utils._PUBKEY_FILE_NAME}
      should_fail = (fail_wrong_payload_type or fail_mismatched_block_size or
                     fail_excess_data)
      if should_fail:
        self.assertRaises(update_payload.PayloadError,
                          payload_checker.Run, **dargs)
      else:
        self.assertIsNone(payload_checker.Run(**dargs))


# This implements a generic API, hence the occasional unused args.
# pylint: disable=W0613
def ValidateCheckOperationTest(op_type_name, is_last, allow_signature,
                               allow_unhashed, fail_src_extents,
                               fail_dst_extents,
                               fail_mismatched_data_offset_length,
                               fail_missing_dst_extents, fail_src_length,
                               fail_dst_length, fail_data_hash,
                               fail_prev_data_offset):
  """Returns True iff the combination of arguments represents a valid test."""
  op_type = _OpTypeByName(op_type_name)

  # REPLACE/REPLACE_BZ operations don't read data from src partition.
  if (op_type in (common.OpType.REPLACE, common.OpType.REPLACE_BZ) and (
      fail_src_extents or fail_src_length)):
    return False

  # MOVE operations don't carry data.
  if (op_type == common.OpType.MOVE and (
      fail_mismatched_data_offset_length or fail_data_hash or
      fail_prev_data_offset)):
    return False

  return True


def TestMethodBody(run_method_name, run_dargs):
  """Returns a function that invokes a named method with named arguments."""
  return lambda self: getattr(self, run_method_name)(**run_dargs)


def AddParametricTests(tested_method_name, arg_space, validate_func=None):
  """Enumerates and adds specific parametric tests to PayloadCheckerTest.

  This function enumerates a space of test parameters (defined by arg_space),
  then binds a new, unique method name in PayloadCheckerTest to a test function
  that gets handed the said parameters. This is a preferable approach to doing
  the enumeration and invocation during the tests because this way each test is
  treated as a complete run by the unittest framework, and so benefits from the
  usual setUp/tearDown mechanics.

  Args:
    tested_method_name: name of the tested PayloadChecker method
    arg_space: a dictionary containing variables (keys) and lists of values
               (values) associated with them
    validate_func: a function used for validating test argument combinations

  """
  for value_tuple in itertools.product(*arg_space.itervalues()):
    run_dargs = dict(zip(arg_space.iterkeys(), value_tuple))
    if validate_func and not validate_func(**run_dargs):
      continue
    run_method_name = 'Do%sTest' % tested_method_name
    test_method_name = 'test%s' % tested_method_name
    for arg_key, arg_val in run_dargs.iteritems():
      if arg_val or type(arg_val) is int:
        test_method_name += '__%s=%s' % (arg_key, arg_val)
    setattr(PayloadCheckerTest, test_method_name,
            TestMethodBody(run_method_name, run_dargs))


def AddAllParametricTests():
  """Enumerates and adds all parametric tests to PayloadCheckerTest."""
  # Add all _CheckElem() test cases.
  AddParametricTests('AddElem',
                     {'linebreak': (True, False),
                      'indent': (0, 1, 2),
                      'convert': (str, lambda s: s[::-1]),
                      'is_present': (True, False),
                      'is_mandatory': (True, False),
                      'is_submsg': (True, False)})

  # Add all _Add{Mandatory,Optional}Field tests.
  AddParametricTests('AddField',
                     {'is_mandatory': (True, False),
                      'linebreak': (True, False),
                      'indent': (0, 1, 2),
                      'convert': (str, lambda s: s[::-1]),
                      'is_present': (True, False)})

  # Add all _Add{Mandatory,Optional}SubMsg tests.
  AddParametricTests('AddSubMsg',
                     {'is_mandatory': (True, False),
                      'is_present': (True, False)})

  # Add all _CheckManifest() test cases.
  AddParametricTests('CheckManifest',
                     {'fail_mismatched_block_size': (True, False),
                      'fail_bad_sigs': (True, False),
                      'fail_mismatched_oki_ori': (True, False),
                      'fail_bad_oki': (True, False),
                      'fail_bad_ori': (True, False),
                      'fail_bad_nki': (True, False),
                      'fail_bad_nri': (True, False),
                      'fail_missing_ops': (True, False),
                      'fail_old_kernel_fs_size': (True, False),
                      'fail_old_rootfs_fs_size': (True, False),
                      'fail_new_kernel_fs_size': (True, False),
                      'fail_new_rootfs_fs_size': (True, False)})

  # Add all _CheckOperation() test cases.
  AddParametricTests('CheckOperation',
                     {'op_type_name': ('REPLACE', 'REPLACE_BZ', 'MOVE',
                                       'BSDIFF'),
                      'is_last': (True, False),
                      'allow_signature': (True, False),
                      'allow_unhashed': (True, False),
                      'fail_src_extents': (True, False),
                      'fail_dst_extents': (True, False),
                      'fail_mismatched_data_offset_length': (True, False),
                      'fail_missing_dst_extents': (True, False),
                      'fail_src_length': (True, False),
                      'fail_dst_length': (True, False),
                      'fail_data_hash': (True, False),
                      'fail_prev_data_offset': (True, False)},
                     validate_func=ValidateCheckOperationTest)

  # Add all _CheckOperations() test cases.
  AddParametricTests('CheckOperations',
                     {'fail_bad_type': (True, False),
                      'fail_nonexhaustive_full_update': (True, False)})

  # Add all _CheckOperations() test cases.
  AddParametricTests('CheckSignatures',
                     {'fail_empty_sigs_blob': (True, False),
                      'fail_missing_pseudo_op': (True, False),
                      'fail_mismatched_pseudo_op': (True, False),
                      'fail_sig_missing_fields': (True, False),
                      'fail_unknown_sig_version': (True, False),
                      'fail_incorrect_sig': (True, False)})

  # Add all Run() test cases.
  AddParametricTests('Run',
                     {'fail_wrong_payload_type': (True, False),
                      'fail_invalid_block_size': (True, False),
                      'fail_mismatched_block_size': (True, False),
                      'fail_excess_data': (True, False)})


if __name__ == '__main__':
  AddAllParametricTests()
  unittest.main()
