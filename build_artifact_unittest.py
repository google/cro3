#!/usr/bin/python2
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for build_artifact module.

These unit tests take tarball from google storage locations to fully test
the artifact download process. Please make sure to set up your boto file.
"""

from __future__ import print_function

import itertools
import os
import random
import shutil
import subprocess
import tempfile
import unittest

import mox

import build_artifact
import devserver_constants
import downloader


_VERSION = 'R26-3646.0.0-rc1'
_TEST_GOLO_ARCHIVE = (
    'gs://chromeos-image-archive/x86-generic-chromium-pfq/R26-3646.0.0-rc1')
_TEST_NON_EXISTING_GOLO_ARCHIVE = (
    'gs://chromeos-image-archive/x86-generic-chromium-pfq/R26-no_such_build')

_TEST_GOLO_ARCHIVE_TEST_TARBALL_CONTENT = [
    'autotest/test_suites/control.PGO_record',
    'autotest/test_suites/control.au',
    'autotest/test_suites/control.audio',
    'autotest/test_suites/control.browsertests',
    'autotest/test_suites/control.bvt',
    'autotest/test_suites/control.dummy',
    'autotest/test_suites/control.enterprise',
    'autotest/test_suites/control.enterprise_enroll',
    'autotest/test_suites/control.faft_dev',
    'autotest/test_suites/control.faft_ec',
    'autotest/test_suites/control.faft_normal',
    'autotest/test_suites/control.graphics',
    'autotest/test_suites/control.graphicsGLES',
    'autotest/test_suites/control.hwqual',
    'autotest/test_suites/control.kernel_daily_benchmarks',
    'autotest/test_suites/control.kernel_daily_regression',
    'autotest/test_suites/control.kernel_per-build_benchmarks',
    'autotest/test_suites/control.kernel_per-build_regression',
    'autotest/test_suites/control.kernel_weekly_regression',
    'autotest/test_suites/control.link_perf',
    'autotest/test_suites/control.network3g',
    'autotest/test_suites/control.network3g_gobi',
    'autotest/test_suites/control.network_wifi',
    'autotest/test_suites/control.onccell',
    'autotest/test_suites/control.pagecycler',
    'autotest/test_suites/control.perfalerts',
    'autotest/test_suites/control.power_build',
    'autotest/test_suites/control.power_daily',
    'autotest/test_suites/control.power_requirements',
    'autotest/test_suites/control.pyauto',
    'autotest/test_suites/control.pyauto_basic',
    'autotest/test_suites/control.pyauto_endurance',
    'autotest/test_suites/control.pyauto_perf',
    'autotest/test_suites/control.regression',
    'autotest/test_suites/control.security',
    'autotest/test_suites/control.servo',
    'autotest/test_suites/control.smoke',
    'autotest/test_suites/control.sync',
    'autotest/test_suites/control.vda',
    'autotest/test_suites/control.video',
    'autotest/test_suites/control.webrtc',
    'autotest/test_suites/control.wificell',
    'autotest/test_suites/control.wifichaos',
    'autotest/test_suites/dependency_info',
    'autotest/test_suites/dev_harness.py',
]

_TEST_GOLO_ARCHIVE_IMAGE_ZIPFILE_CONTENT = [
    'au-generator.zip',
    'boot.config',
    'boot.desc',
    'chromiumos_qemu_image.bin',
    'chromiumos_test_image.bin',
    'config.txt',
    'mount_image.sh',
    'oem.image',
    'pack_partitions.sh',
    'umount_image.sh',
    'unpack_partitions.sh',
]


# Different as the above does not have deltas (for smaller artifacts).
_DELTA_VERSION = 'R26-3645.0.0'
_TEST_GOLO_FOR_DELTAS = (
    'gs://chromeos-image-archive/x86-mario-release/R26-3645.0.0')


# pylint: disable=W0212
class BuildArtifactTest(mox.MoxTestBase):
  """Test different BuildArtifact operations."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.work_dir = tempfile.mkdtemp('build_artifact_unittest')

  def tearDown(self):
    shutil.rmtree(self.work_dir)

  def _CheckMarker(self, marker_file, installed_files):
    with open(os.path.join(self.work_dir, marker_file)) as f:
      self.assertItemsEqual(installed_files, [line.strip() for line in f])

  def testBundledArtifactTypes(self):
    """Tests that all known bundled artifacts are either zip or tar files."""
    known_names = ['zip', '.tgz', '.tar', 'tar.bz2', 'tar.xz', 'tar.gz']
    for d in itertools.chain(*build_artifact.chromeos_artifact_map.values()):
      if issubclass(d, build_artifact.BundledArtifact):
        self.assertTrue(any(d.ARTIFACT_NAME.endswith(name)
                            for name in known_names))

  def testProcessBuildArtifact(self):
    """Processes a real tarball from GSUtil and stages it."""
    artifact = build_artifact.Artifact(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION)
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(
        artifact.installed_files,
        [os.path.join(self.work_dir, build_artifact.TEST_SUITES_FILE)])
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, build_artifact.TEST_SUITES_FILE)))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testProcessTarball(self):
    """Downloads a real tarball and untars it."""
    artifact = build_artifact.BundledArtifact(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION)
    expected_installed_files = [
        os.path.join(self.work_dir, filename)
        for filename in ([build_artifact.TEST_SUITES_FILE] +
                         _TEST_GOLO_ARCHIVE_TEST_TARBALL_CONTENT)]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(artifact.installed_files, expected_installed_files)
    self.assertTrue(os.path.isdir(os.path.join(
        self.work_dir, 'autotest', 'test_suites')))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testProcessTarballWithFile(self):
    """Downloads a real tarball and only untars one file from it."""
    file_to_download = 'autotest/test_suites/control.au'
    artifact = build_artifact.BundledArtifact(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION,
        files_to_extract=[file_to_download])
    expected_installed_files = [
        os.path.join(self.work_dir, filename)
        for filename in [build_artifact.TEST_SUITES_FILE] + [file_to_download]]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(artifact.installed_files, expected_installed_files)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, file_to_download)))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testDownloadAutotest(self):
    """Downloads a real autotest tarball for test."""
    self.mox.StubOutWithMock(build_artifact.AutotestTarball, '_Extract')
    artifact = build_artifact.AutotestTarball(
        build_artifact.AUTOTEST_FILE, self.work_dir, _VERSION,
        files_to_extract=None, exclude=['autotest/test_suites'])

    install_dir = self.work_dir
    artifact.staging_dir = install_dir
    self.mox.StubOutWithMock(subprocess, 'check_call')
    subprocess.check_call(mox.In('autotest/utils/packager.py'), cwd=install_dir)
    self.mox.StubOutWithMock(downloader.GoogleStorageDownloader, 'Wait')
    self.mox.StubOutWithMock(artifact, '_UpdateName')
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    dl.Wait(artifact.name, False, 1)
    artifact._UpdateName(mox.IgnoreArg())
    dl.Fetch(artifact.name, install_dir)
    artifact._Extract()
    self.mox.ReplayAll()
    artifact.Process(dl, True)
    self.mox.VerifyAll()
    self.assertItemsEqual(artifact.installed_files, [])
    self.assertTrue(os.path.isdir(
        os.path.join(self.work_dir, 'autotest', 'packages')))
    self._CheckMarker(artifact.marker_name, [])

  def testAUTestPayloadBuildArtifact(self):
    """Downloads a real tarball and treats it like an AU payload."""
    artifact = build_artifact.AUTestPayload(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION)
    expected_installed_files = [
        os.path.join(self.work_dir, devserver_constants.UPDATE_FILE)]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(artifact.installed_files, expected_installed_files)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, devserver_constants.UPDATE_FILE)))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testDeltaPayloadsArtifact(self):
    """Downloads delta paylaods from test bucket."""
    nton = build_artifact.DeltaPayloadNtoN(self.work_dir, _DELTA_VERSION)
    mton = build_artifact.DeltaPayloadMtoN(self.work_dir, _DELTA_VERSION)
    delta_installed_files = ('update.gz', 'stateful.tgz')
    nton_dir = os.path.join(self.work_dir, 'au', '%s_nton' % _DELTA_VERSION)
    mton_dir = os.path.join(self.work_dir, 'au', '%s_mton' % _DELTA_VERSION)
    dl = downloader.GoogleStorageDownloader(self.work_dir,
                                            _TEST_GOLO_FOR_DELTAS)
    nton.Process(dl, False)
    mton.Process(dl, False)
    self.assertItemsEqual(nton.installed_files,
                          [os.path.join(nton_dir, filename)
                           for filename in delta_installed_files])
    self.assertItemsEqual(mton.installed_files,
                          [os.path.join(mton_dir, filename)
                           for filename in delta_installed_files])
    self.assertTrue(os.path.exists(os.path.join(nton_dir, 'update.gz')))
    self.assertTrue(os.path.exists(os.path.join(mton_dir, 'update.gz')))
    self._CheckMarker(nton.marker_name, nton.installed_files)
    self._CheckMarker(mton.marker_name, mton.installed_files)

  def testImageUnzip(self):
    """Downloads and stages a zip file and extracts a test image."""
    files_to_extract = ['chromiumos_test_image.bin']
    artifact = build_artifact.BundledArtifact(
        build_artifact.IMAGE_FILE, self.work_dir, _VERSION,
        files_to_extract=files_to_extract)
    expected_installed_files = [
        os.path.join(self.work_dir, filename)
        for filename in [build_artifact.IMAGE_FILE] + files_to_extract]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(expected_installed_files, artifact.installed_files)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'chromiumos_test_image.bin')))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testImageUnzipWithExcludes(self):
    """Downloads and stages a zip file while excluding all large files."""
    artifact = build_artifact.BundledArtifact(
        build_artifact.IMAGE_FILE, self.work_dir, _VERSION, exclude=['*.bin'])
    expected_extracted_files = [
        filename for filename in _TEST_GOLO_ARCHIVE_IMAGE_ZIPFILE_CONTENT
        if not filename.endswith('.bin')]
    expected_installed_files = [
        os.path.join(self.work_dir, filename)
        for filename in [build_artifact.IMAGE_FILE] + expected_extracted_files]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)
    self.assertItemsEqual(expected_installed_files, artifact.installed_files)
    self.assertFalse(os.path.exists(os.path.join(
        self.work_dir, 'chromiumos_test_image.bin')))
    self._CheckMarker(artifact.marker_name, artifact.installed_files)

  def testArtifactFactory(self):
    """Tests that BuildArtifact works for both named and file artifacts."""
    name_artifact = 'test_suites' # This file is in every real GS dir.
    file_artifact = 'metadata.json' # This file is in every real GS dir.
    factory = build_artifact.ChromeOSArtifactFactory(
        self.work_dir, [name_artifact], [file_artifact], _VERSION)
    artifacts = factory.RequiredArtifacts()
    self.assertEqual(len(artifacts), 2)
    expected_installed_files_0 = [
        os.path.join(self.work_dir, filename) for filename
        in ([build_artifact.TEST_SUITES_FILE] +
            _TEST_GOLO_ARCHIVE_TEST_TARBALL_CONTENT)]
    expected_installed_files_1 = [os.path.join(self.work_dir, file_artifact)]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifacts[0].Process(dl, False)
    artifacts[1].Process(dl, False)
    self.assertItemsEqual(artifacts[0].installed_files,
                          expected_installed_files_0)
    self.assertItemsEqual(artifacts[1].installed_files,
                          expected_installed_files_1)
    # Test suites directory exists.
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'autotest', 'test_suites')))
    # File artifact was staged.
    self.assertTrue(os.path.exists(os.path.join(self.work_dir,
                                                file_artifact)))
    self._CheckMarker(artifacts[0].marker_name, artifacts[0].installed_files)
    self._CheckMarker(artifacts[1].marker_name, artifacts[1].installed_files)

  def testProcessBuildArtifactWithException(self):
    """Test processing a non-existing artifact from GSUtil."""
    artifact = build_artifact.Artifact(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION)
    try:
      dl = downloader.GoogleStorageDownloader(self.work_dir,
                                              _TEST_NON_EXISTING_GOLO_ARCHIVE)
      artifact.Process(dl, False)
    except Exception as e:
      expected_exception = e
    exception = artifact.GetException()
    self.assertEqual(str(exception), str(expected_exception))

  def testArtifactStaged(self):
    """Tests the artifact staging verification logic."""
    artifact = build_artifact.BundledArtifact(
        build_artifact.TEST_SUITES_FILE, self.work_dir, _VERSION)
    expected_installed_files = [
        os.path.join(self.work_dir, filename)
        for filename in ([build_artifact.TEST_SUITES_FILE] +
                         _TEST_GOLO_ARCHIVE_TEST_TARBALL_CONTENT)]
    dl = downloader.GoogleStorageDownloader(self.work_dir, _TEST_GOLO_ARCHIVE)
    artifact.Process(dl, False)

    # Check that it works when all files are there.
    self.assertTrue(artifact.ArtifactStaged())

    # Remove an arbitrary file among the ones staged, ensure the check fails
    # and that the marker files is removed.
    os.remove(random.choice(expected_installed_files))
    self.assertTrue(os.path.exists(os.path.join(self.work_dir,
                                                artifact.marker_name)))
    self.assertFalse(artifact.ArtifactStaged())
    self.assertFalse(os.path.exists(os.path.join(self.work_dir,
                                                 artifact.marker_name)))


if __name__ == '__main__':
  unittest.main()
