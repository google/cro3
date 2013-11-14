#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing classes that wrap artifact downloads."""

import os
import pickle
import re
import shutil
import subprocess

import artifact_info
import common_util
import devserver_constants
import gsutil_util
import log_util


_AU_BASE = 'au'
_NTON_DIR_SUFFIX = '_nton'
_MTON_DIR_SUFFIX = '_mton'

############ Actual filenames of artifacts in Google Storage ############

AU_SUITE_FILE = 'au_control.tar.bz2'
PAYGEN_AU_SUITE_FILE_TEMPLATE = 'paygen_au_%(channel)s_control.tar.bz2'
AUTOTEST_FILE = 'autotest.tar'
AUTOTEST_COMPRESSED_FILE = 'autotest.tar.bz2'
DEBUG_SYMBOLS_FILE = 'debug.tgz'
FACTORY_FILE = 'ChromeOS-factory*zip'
FIRMWARE_FILE = 'firmware_from_source.tar.bz2'
IMAGE_FILE = 'image.zip'
TEST_SUITES_FILE = 'test_suites.tar.bz2'

_build_artifact_locks = common_util.LockDict()


class ArtifactDownloadError(Exception):
  """Error used to signify an issue processing an artifact."""
  pass


class BuildArtifact(log_util.Loggable):
  """Wrapper around an artifact to download from gsutil.

  The purpose of this class is to download objects from Google Storage
  and install them to a local directory. There are two main functions, one to
  download/prepare the artifacts in to a temporary staging area and the second
  to stage it into its final destination.

  IMPORTANT!  (i) `name' is a glob expression by default (and not a regex), be
  attentive when adding new artifacts; (ii) name matching semantics differ
  between a glob (full name string match) and a regex (partial match).

  Class members:
    archive_url: An archive URL.
    name: Name given for artifact; in fact, it is a pattern that captures the
          names of files contained in the artifact. This can either be an
          ordinary shell-style glob (the default), or a regular expression (if
          is_regex_name is True).
    is_regex_name: Whether the name value is a regex (default: glob).
    build: The version of the build i.e. R26-2342.0.0.
    marker_name: Name used to define the lock marker for the artifacts to
                 prevent it from being re-downloaded. By default based on name
                 but can be overriden by children.
    exception_file_path: Path to a file containing the serialized exception,
                         which was raised in Process method. The file is located
                         in the parent folder of install_dir, since the
                         install_dir will be deleted if the build does not
                         existed.
    install_path: Path to artifact.
    install_dir: The final location where the artifact should be staged to.
    single_name: If True the name given should only match one item. Note, if not
                 True, self.name will become a list of items returned.
    installed_files: A list of files that were the final result of downloading
                     and setting up the artifact.
    store_installed_files: Whether the list of installed files is stored in the
                           marker file.
  """

  def __init__(self, install_dir, archive_url, name, build,
               is_regex_name=False):
    """Constructor.

    Args:
      install_dir: Where to install the artifact.
      archive_url: The Google Storage path to find the artifact.
      name: Identifying name to be used to find/store the artifact.
      build: The name of the build e.g. board/release.
      is_regex_name: Whether the name pattern is a regex (default: glob).
    """
    super(BuildArtifact, self).__init__()

    # In-memory lock to keep the devserver from colliding with itself while
    # attempting to stage the same artifact.
    self._process_lock = None

    self.archive_url = archive_url
    self.name = name
    self.is_regex_name = is_regex_name
    self.build = build

    self.marker_name = '.' + self._SanitizeName(name)

    exception_file_name = ('.' + self._SanitizeName(build) + self.marker_name +
                           '.exception')
    # The exception file needs to be located in parent folder, since the
    # install_dir will be deleted is the build does not exist.
    self.exception_file_path = os.path.join(os.path.dirname(install_dir),
                                            exception_file_name)

    self.install_path = None

    self.install_dir = install_dir

    self.single_name = True

    self.installed_files = []
    self.store_installed_files = True

  @staticmethod
  def _SanitizeName(name):
    """Sanitizes name to be used for creating a file on the filesystem.

    '.','/' and '*' have special meaning in FS lingo. Replace them with words.

    Args:
      name: A file name/path.
    Returns:
      The sanitized name/path.
    """
    return name.replace('*', 'STAR').replace('.', 'DOT').replace('/', 'SLASH')

  def ArtifactStaged(self):
    """Returns True if artifact is already staged.

    This checks for (1) presence of the artifact marker file, and (2) the
    presence of each installed file listed in this marker. Both must hold for
    the artifact to be considered staged. Note that this method is safe for use
    even if the artifacts were not stageed by this instance, as it is assumed
    that any BuildArtifact instance that did the staging wrote the list of
    files actually installed into the marker.
    """
    marker_file = os.path.join(self.install_dir, self.marker_name)

    # If the marker is missing, it's definitely not staged.
    if not os.path.exists(marker_file):
      return False

    # We want to ensure that every file listed in the marker is actually there.
    if self.store_installed_files:
      with open(marker_file) as f:
        files = [line.strip() for line in f]

      # Check to see if any of the purportedly installed files are missing, in
      # which case the marker is outdated and should be removed.
      missing_files = [fname for fname in files if not os.path.exists(fname)]
      if missing_files:
        self._Log('***ATTENTION*** %s files listed in %s are missing:\n%s',
                  'All' if len(files) == len(missing_files) else 'Some',
                  marker_file, '\n'.join(missing_files))
        os.remove(marker_file)
        return False

    return True

  def _MarkArtifactStaged(self):
    """Marks the artifact as staged."""
    with open(os.path.join(self.install_dir, self.marker_name), 'w') as f:
      f.write('\n'.join(self.installed_files))

  def _WaitForArtifactToExist(self, timeout, update_name=True):
    """Waits for artifact to exist and sets self.name to appropriate name.

    Args:
      timeout: How long to wait for artifact to become available.
      update_name: If False, don't actually update self.name.
    Raises:
      ArtifactDownloadError: An error occurred when obtaining artifact.
    """
    names = gsutil_util.GetGSNamesWithWait(
        self.name, self.archive_url, str(self), timeout=timeout,
        is_regex_pattern=self.is_regex_name)
    if not names:
      raise ArtifactDownloadError('Could not find %s in Google Storage' %
                                  self.name)

    if self.single_name:
      if len(names) > 1:
        raise ArtifactDownloadError('Too many artifacts match %s' % self.name)

      new_name = names[0]
    else:
      new_name = names

    if update_name:
      self.name = new_name

  def _Download(self):
    """Downloads artifact from Google Storage to a local directory."""
    gs_path = '/'.join([self.archive_url, self.name])
    self.install_path = os.path.join(self.install_dir, self.name)
    gsutil_util.DownloadFromGS(gs_path, self.install_path)

  def _Setup(self):
    """Process the downloaded content, update the list of installed files."""
    # In this primitive case, what was downloaded (has to be a single file) is
    # what's installed.
    self.installed_files = [self.install_path]

  def _ClearException(self):
    """Delete any existing exception saved for this artifact."""
    if os.path.exists(self.exception_file_path):
      os.remove(self.exception_file_path)

  def _SaveException(self, e):
    """Save the exception to a file for downloader.IsStaged to retrieve.

    Args:
      e: Exception object to be saved.
    """
    with open(self.exception_file_path, 'w') as f:
      pickle.dump(e, f)

  def GetException(self):
    """Retrieve any exception that was raised in Process method.

    Returns:
      An Exception object that was raised when trying to process the artifact.
      Return None if no exception was found.
    """
    if not os.path.exists(self.exception_file_path):
      return None
    with open(self.exception_file_path, 'r') as f:
      return pickle.load(f)

  def Process(self, no_wait):
    """Main call point to all artifacts. Downloads and Stages artifact.

    Downloads and Stages artifact from Google Storage to the install directory
    specified in the constructor. It multi-thread safe and does not overwrite
    the artifact if it's already been downloaded or being downloaded. After
    processing, leaves behind a marker to indicate to future invocations that
    the artifact has already been staged based on the name of the artifact.

    Do not override as it modifies important private variables, ensures thread
    safety, and maintains cache semantics.

    Note: this may be a blocking call when the artifact is already in the
    process of being staged.

    Args:
      no_wait: If True, don't block waiting for artifact to exist if we fail to
               immediately find it.

    Raises:
      ArtifactDownloadError: If the artifact fails to download from Google
                             Storage for any reason or that the regexp
                             defined by name is not specific enough.
    """
    if not self._process_lock:
      self._process_lock = _build_artifact_locks.lock(
          os.path.join(self.install_dir, self.name))

    with self._process_lock:
      common_util.MkDirP(self.install_dir)
      if not self.ArtifactStaged():
        try:
          # Delete any existing exception saved for this artifact.
          self._ClearException()
          # If the artifact should already have been uploaded, don't waste
          # cycles waiting around for it to exist.
          timeout = 1 if no_wait else 10
          self._WaitForArtifactToExist(timeout)
          self._Download()
          self._Setup()
          self._MarkArtifactStaged()
        except Exception as e:
          # Save the exception to a file for downloader.IsStaged to retrieve.
          self._SaveException(e)

          # Convert an unknown exception into an ArtifactDownloadError.
          if type(e) is ArtifactDownloadError:
            raise
          else:
            raise ArtifactDownloadError('An error occurred: %s' % e)
      else:
        self._Log('%s is already staged.', self)

  def __str__(self):
    """String representation for the download."""
    return '->'.join(['%s/%s' % (self.archive_url, self.name),
                      self.install_dir])

  def __repr__(self):
    return str(self)


class AUTestPayloadBuildArtifact(BuildArtifact):
  """Wrapper for AUTest delta payloads which need additional setup."""

  def _Setup(self):
    super(AUTestPayloadBuildArtifact, self)._Setup()

    # Rename to update.gz.
    install_path = os.path.join(self.install_dir, self.name)
    new_install_path = os.path.join(self.install_dir,
                                    devserver_constants.UPDATE_FILE)
    shutil.move(install_path, new_install_path)

    # Reflect the rename in the list of installed files.
    self.installed_files.remove(install_path)
    self.installed_files = [new_install_path]


# TODO(sosa): Change callers to make this artifact more sane.
class DeltaPayloadsArtifact(BuildArtifact):
  """Delta payloads from the archive_url.

  This artifact is super strange. It custom handles directories and
  pulls in all delta payloads. We can't specify exactly what we want
  because unlike other artifacts, this one does not conform to something a
  client might know. The client doesn't know the version of n-1 or whether it
  was even generated.

  IMPORTANT! Note that this artifact simply ignores the `name' argument because
  that name is derived internally in accordance with sub-artifacts. Also note
  the different types of names (in fact, file name patterns) used for the
  different sub-artifacts.
  """

  def __init__(self, *args):
    super(DeltaPayloadsArtifact, self).__init__(*args)
    # Override the name field, we know what it should be.
    self.name = '*_delta_*'
    self.is_regex_name = False
    self.single_name = False  # Expect multiple deltas

    # We use a regular glob for the N-to-N delta payload.
    nton_name = 'chromeos_%s*_delta_*' % self.build
    # We use a regular expression for the M-to-N delta payload.
    mton_name = ('chromeos_(?!%s).*_delta_.*' % re.escape(self.build))

    nton_install_dir = os.path.join(self.install_dir, _AU_BASE,
                                    self.build + _NTON_DIR_SUFFIX)
    mton_install_dir = os.path.join(self.install_dir, _AU_BASE,
                                    self.build + _MTON_DIR_SUFFIX)
    self._sub_artifacts = [
        AUTestPayloadBuildArtifact(mton_install_dir, self.archive_url,
                                   mton_name, self.build, is_regex_name=True),
        AUTestPayloadBuildArtifact(nton_install_dir, self.archive_url,
                                   nton_name, self.build)]

  def _Download(self):
    """With sub-artifacts we do everything in _Setup()."""
    pass

  def _Setup(self):
    """Process each sub-artifact. Only error out if none can be found."""
    for artifact in self._sub_artifacts:
      try:
        artifact.Process(no_wait=True)
        # Setup symlink so that AU will work for this payload.
        stateful_update_symlink = os.path.join(
            artifact.install_dir, devserver_constants.STATEFUL_FILE)
        os.symlink(
            os.path.join(os.pardir, os.pardir,
                         devserver_constants.STATEFUL_FILE),
            stateful_update_symlink)

        # Aggregate sub-artifact file lists, including stateful symlink.
        self.installed_files += artifact.installed_files
        self.installed_files.append(stateful_update_symlink)
      except ArtifactDownloadError as e:
        self._Log('Could not process %s: %s', artifact, e)
        raise


class BundledBuildArtifact(BuildArtifact):
  """A single build artifact bundle e.g. zip file or tar file."""

  def __init__(self, install_dir, archive_url, name, build,
               is_regex_name=False, files_to_extract=None, exclude=None):
    """Takes BuildArtifact args with some additional ones.

    Args:
      install_dir: See superclass.
      archive_url: See superclass.
      name: See superclass.
      build: See superclass.
      is_regex_name: See superclass.
      files_to_extract: A list of files to extract. If set to None, extract
                        all files.
      exclude: A list of files to exclude. If None, no files are excluded.
    """
    super(BundledBuildArtifact, self).__init__(
        install_dir, archive_url, name, build, is_regex_name=is_regex_name)
    self._files_to_extract = files_to_extract
    self._exclude = exclude

    # We modify the marker so that it is unique to what was staged.
    if files_to_extract:
      self.marker_name = self._SanitizeName(
          '_'.join(['.' + self.name] + files_to_extract))

  def _Extract(self):
    """Extracts the bundle into install_dir. Must be overridden.

    If set, uses files_to_extract to only extract those items. If set, use
    exclude to exclude specific files. In any case, this must return the list
    of files extracted (absolute paths).
    """
    raise NotImplementedError()

  def _Setup(self):
    extract_result = self._Extract()
    if self.store_installed_files:
      # List both the archive and the extracted files.
      self.installed_files.append(self.install_path)
      self.installed_files.extend(extract_result)


class TarballBuildArtifact(BundledBuildArtifact):
  """Artifact for tar and tarball files."""

  def _Extract(self):
    """Extracts a tarball using tar.

    Detects whether the tarball is compressed or not based on the file
    extension and extracts the tarball into the install_path.
    """
    try:
      return common_util.ExtractTarball(self.install_path, self.install_dir,
                                        files_to_extract=self._files_to_extract,
                                        excluded_files=self._exclude,
                                        return_extracted_files=True)
    except common_util.CommonUtilError as e:
      raise ArtifactDownloadError(str(e))


class AutotestTarballBuildArtifact(TarballBuildArtifact):
  """Wrapper around the autotest tarball to download from gsutil."""

  def __init__(self, *args, **dargs):
    super(AutotestTarballBuildArtifact, self).__init__(*args, **dargs)
    # We don't store/check explicit file lists in Autotest tarball markers;
    # this can get huge and unwieldy, and generally make little sense.
    self.store_installed_files = False

  def _Setup(self):
    """Extracts the tarball into the install path excluding test suites."""
    super(AutotestTarballBuildArtifact, self)._Setup()

    # Deal with older autotest packages that may not be bundled.
    autotest_dir = os.path.join(self.install_dir,
                                devserver_constants.AUTOTEST_DIR)
    autotest_pkgs_dir = os.path.join(autotest_dir, 'packages')
    if not os.path.exists(autotest_pkgs_dir):
      os.makedirs(autotest_pkgs_dir)

    if not os.path.exists(os.path.join(autotest_pkgs_dir, 'packages.checksum')):
      cmd = ['autotest/utils/packager.py', 'upload', '--repository',
             autotest_pkgs_dir, '--all']
      try:
        subprocess.check_call(cmd, cwd=self.install_dir)
      except subprocess.CalledProcessError, e:
        raise ArtifactDownloadError(
            'Failed to create autotest packages!:\n%s' % e)
    else:
      self._Log('Using pre-generated packages from autotest')


class ZipfileBuildArtifact(BundledBuildArtifact):
  """A downloadable artifact that is a zipfile."""

  def _RunUnzip(self, list_only):
    # Unzip is weird. It expects its args before any excludes and expects its
    # excludes in a list following the -x.
    cmd = ['unzip', '-qql' if list_only else '-o', self.install_path]
    if not list_only:
      cmd += ['-d', self.install_dir]

    if self._files_to_extract:
      cmd.extend(self._files_to_extract)

    if self._exclude:
      cmd.append('-x')
      cmd.extend(self._exclude)

    try:
      return subprocess.check_output(cmd).strip('\n').splitlines()
    except subprocess.CalledProcessError, e:
      raise ArtifactDownloadError(
          'An error occurred when attempting to unzip %s:\n%s' %
          (self.install_path, e))

  def _Extract(self):
    """Extracts files into the install path."""
    file_list = [os.path.join(self.install_dir, line[30:].strip())
                 for line in self._RunUnzip(True)
                 if not line.endswith('/')]
    if file_list:
      self._RunUnzip(False)

    return file_list


class ImplDescription(object):
  """Data wrapper that describes an artifact's implementation."""

  def __init__(self, artifact_class, name, *additional_args,
               **additional_dargs):
    """Constructor.

    Args:
      artifact_class: BuildArtifact class to use for the artifact.
      name: name to use to identify artifact (see BuildArtifact.name)
      *additional_args: Additional arguments to pass to artifact_class.
      **additional_dargs: Additional named arguments to pass to artifact_class.
    """
    self.artifact_class = artifact_class
    self.name = name
    self.additional_args = additional_args
    self.additional_dargs = additional_dargs

  def __repr__(self):
    return '%s_%s' % (self.artifact_class, self.name)


# Maps artifact names to their implementation description.
# Please note, it is good practice to use constants for these names if you're
# going to re-use the names ANYWHERE else in the devserver code.
ARTIFACT_IMPLEMENTATION_MAP = {
    artifact_info.FULL_PAYLOAD:
    ImplDescription(AUTestPayloadBuildArtifact, '*_full_*'),
    artifact_info.DELTA_PAYLOADS:
    ImplDescription(DeltaPayloadsArtifact, 'DONTCARE'),
    artifact_info.STATEFUL_PAYLOAD:
    ImplDescription(BuildArtifact, devserver_constants.STATEFUL_FILE),

    artifact_info.BASE_IMAGE:
    ImplDescription(ZipfileBuildArtifact, IMAGE_FILE,
                    files_to_extract=[devserver_constants.BASE_IMAGE_FILE]),
    artifact_info.RECOVERY_IMAGE:
    ImplDescription(ZipfileBuildArtifact, IMAGE_FILE,
                    files_to_extract=[devserver_constants.RECOVERY_IMAGE_FILE]),
    artifact_info.DEV_IMAGE:
    ImplDescription(ZipfileBuildArtifact, IMAGE_FILE,
                    files_to_extract=[devserver_constants.IMAGE_FILE]),
    artifact_info.TEST_IMAGE:
    ImplDescription(ZipfileBuildArtifact, IMAGE_FILE,
                    files_to_extract=[devserver_constants.TEST_IMAGE_FILE]),

    artifact_info.AUTOTEST:
    ImplDescription(AutotestTarballBuildArtifact, AUTOTEST_FILE,
                    files_to_extract=None,
                    exclude=['autotest/test_suites']),
    artifact_info.TEST_SUITES:
    ImplDescription(TarballBuildArtifact, TEST_SUITES_FILE),
    artifact_info.AU_SUITE:
    ImplDescription(TarballBuildArtifact, AU_SUITE_FILE),

    artifact_info.FIRMWARE:
    ImplDescription(BuildArtifact, FIRMWARE_FILE),
    artifact_info.SYMBOLS:
    ImplDescription(TarballBuildArtifact, DEBUG_SYMBOLS_FILE,
                    files_to_extract=['debug/breakpad']),

    artifact_info.FACTORY_IMAGE:
    ImplDescription(ZipfileBuildArtifact, FACTORY_FILE,
                    files_to_extract=[devserver_constants.FACTORY_IMAGE_FILE])
}

# Add all the paygen_au artifacts in one go.
ARTIFACT_IMPLEMENTATION_MAP.update({
    artifact_info.PAYGEN_AU_SUITE_TEMPLATE % {'channel': c}:
    ImplDescription(
        TarballBuildArtifact, PAYGEN_AU_SUITE_FILE_TEMPLATE % {'channel': c})
    for c in devserver_constants.CHANNELS
})


class ArtifactFactory(object):
  """A factory class that generates build artifacts from artifact names."""

  def __init__(self, download_dir, archive_url, artifacts, files,
               build):
    """Initalizes the member variables for the factory.

    Args:
      download_dir: A directory to which artifacts are downloaded.
      archive_url: the Google Storage url of the bucket where the debug
                   symbols for the desired build are stored.
      artifacts: List of artifacts to stage. These artifacts must be
                 defined in artifact_info.py and have a mapping in the
                 ARTIFACT_IMPLEMENTATION_MAP.
      files: List of files to stage. These files are just downloaded and staged
             as files into the download_dir.
      build: The name of the build.
    """
    self.download_dir = download_dir
    self.archive_url = archive_url
    self.artifacts = artifacts
    self.files = files
    self.build = build

  @staticmethod
  def _GetDescriptionComponents(name, is_artifact):
    """Returns components for constructing a BuildArtifact.

    Args:
      name: The artifact name / file pattern.
      is_artifact: Whether this is a named (True) or file (False) artifact.
    Returns:
      A tuple consisting of the BuildArtifact subclass, name, and additional
      list- and named-arguments.
    Raises:
      KeyError: if artifact doesn't exist in ARTIFACT_IMPLEMENTATION_MAP.
    """

    if is_artifact:
      description = ARTIFACT_IMPLEMENTATION_MAP[name]
    else:
      description = ImplDescription(BuildArtifact, name)

    return (description.artifact_class, description.name,
            description.additional_args, description.additional_dargs)

  def _Artifacts(self, names, is_artifact):
    """Returns the BuildArtifacts from |names|.

    If is_artifact is true, then these names define artifacts that must exist in
    the ARTIFACT_IMPLEMENTATION_MAP. Otherwise, treat as filenames to stage as
    basic BuildArtifacts.

    Args:
      names: A sequence of artifact names.
      is_artifact: Whether this is a named (True) or file (False) artifact.
    Returns:
      An iterable of BuildArtifacts.
    Raises:
      KeyError: if artifact doesn't exist in ARTIFACT_IMPLEMENTATION_MAP.
    """
    artifacts = []
    for name in names:
      artifact_class, path, args, dargs = self._GetDescriptionComponents(
          name, is_artifact)
      artifacts.append(artifact_class(self.download_dir, self.archive_url, path,
                                      self.build, *args, **dargs))

    return artifacts

  def RequiredArtifacts(self):
    """Returns BuildArtifacts for the factory's artifacts.

    Returns:
      An iterable of BuildArtifacts.
    Raises:
      KeyError: if artifact doesn't exist in ARTIFACT_IMPLEMENTATION_MAP.
    """
    artifacts = []
    if self.artifacts:
      artifacts.extend(self._Artifacts(self.artifacts, True))
    if self.files:
      artifacts.extend(self._Artifacts(self.files, False))

    return artifacts

  def OptionalArtifacts(self):
    """Returns BuildArtifacts that should be cached.

    Returns:
      An iterable of BuildArtifacts.
    Raises:
      KeyError: if an optional artifact doesn't exist in
                ARTIFACT_IMPLEMENTATION_MAP yet defined in
                artifact_info.REQUESTED_TO_OPTIONAL_MAP.
    """
    optional_names = set()
    for artifact_name, optional_list in (
        artifact_info.REQUESTED_TO_OPTIONAL_MAP.iteritems()):
      # We are already downloading it.
      if artifact_name in self.artifacts:
        optional_names = optional_names.union(optional_list)

    return self._Artifacts(optional_names - set(self.artifacts), True)


# A simple main to verify correctness of the artifact map when making simple
# name changes.
if __name__ == '__main__':
  print 'ARTIFACT IMPLEMENTATION MAP (for debugging)'
  print 'FORMAT: ARTIFACT -> IMPLEMENTATION (<class>_file)'
  for key, value in sorted(ARTIFACT_IMPLEMENTATION_MAP.items()):
    print '%s -> %s' % (key, value)
