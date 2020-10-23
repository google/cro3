#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file uses 2-space indentations.
# pylint: disable=bad-indentation

# This is contrib-quality code: not all functions/classes are
# documented.
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=class-missing-docstring

# Classes make heavy-use of setattr to dynamically set the attributes
# on an object.  Disable this check which gets confused very
# frequently.
# pylint: disable=no-member

"""Utility script to auto-convert a pre-unibuild board to unibuild."""

import argparse
import datetime
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
# pylint: disable=import-error
import yaml
# pylint: enable=import-error


make_defaults_search_and_destroy_re = re.compile(
    r'(?:^\s*)*(?:^\s*#.*\s*)*^\s*USE="\s*\$\{?USE\}?\s*-unibuild\s*"\s*$',
    re.MULTILINE)


def log(message):
  print('[{}] {}'.format(datetime.datetime.now(), message), file=sys.stderr)


def prepend_all_lines(text, prepend):
  return ''.join(
      '{}{}\n'.format(prepend, line)
      for line in text.splitlines())


def gen_cros_copyright(line_comment='# '):
  return prepend_all_lines(
      """Copyright {} The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.""".format(datetime.datetime.now().strftime('%Y')),
      line_comment)


def yaml_str_representer(dumper, data):
  style = None
  tag = 'tag:yaml.org,2002:str'
  if '\n' in data:
    style = '|'
  return dumper.represent_scalar(tag, data, style)


yaml.add_representer(str, yaml_str_representer)


def format_yaml(config):
  conf_str = yaml.dump(config, indent=2, default_flow_style=False)
  out = gen_cros_copyright()
  out += """
# This board only supports a single config, defined below, as it is a
# migrated pre-unibuild device.
device-config: &device_config\n"""
  out += prepend_all_lines(conf_str, '  ')
  out += """
# Required dunder for chromeos-config to support a single device.
chromeos:
  devices:
    - skus:
        - config: *device_config\n"""
  return out


def generate_vpackage(depends):
  return gen_cros_copyright() + """
EAPI=7

DESCRIPTION="ChromeOS Unibuild Config virtual package"
HOMEPAGE="https://chromium.googlesource.com/chromiumos/platform2/+/master/chromeos-config/README.md"

LICENSE="BSD-Google"
SLOT="0"
KEYWORDS="*"

DEPEND="%(depends)s"
RDEPEND="${DEPEND}"
""" % {
    'depends':
    (''.join('\n\t{}'.format(d) for d in depends) + '\n')
    if len(depends) > 1 else
    ''.join(depends)}


def generate_bsp_ebuild(private=False):
  return gen_cros_copyright() + """
EAPI=7

# cros_workon applies only to ebuild and files directory. Use the
# canonical empty project.
CROS_WORKON_PROJECT="chromiumos/infra/build/empty-project"
CROS_WORKON_LOCALNAME="platform/empty-project"

inherit cros-workon cros-unibuild

DESCRIPTION="ChromeOS model configuration"
HOMEPAGE="https://chromium.googlesource.com/chromiumos/platform2/+/master/chromeos-config/README.md"

LICENSE="BSD-Google"
SLOT="0"
KEYWORDS="~*"

src_install() {
\tinstall%(maybe_private)s_model_files
}
""" % {'maybe_private': '_private' if private else ''}


def generate_firmware_ebuild(board_name):
  return gen_cros_copyright() + """
# Change this version number when any change is made to model.yaml
# in order to trigger an auto-revbump is required.
# VERSION=REVBUMP-0.0.1

EAPI=7
CROS_WORKON_COMMIT=""
CROS_WORKON_TREE=""
CROS_WORKON_LOCALNAME="platform/firmware"
CROS_WORKON_PROJECT="chromiumos/platform/firmware"
CROS_BOARDS=( %(board_name)s )

inherit cros-workon cros-firmware cros-unibuild

DESCRIPTION="Chrome OS Firmware (%(board_name)s)"
HOMEPAGE="http://src.chromium.org"
LICENSE="BSD-Google"
SLOT="0"
KEYWORDS="~*"

RDEPEND=""

# Unified Builds firmware URL's are read from:
#   chromeos-base/chromeos-config-bsp-private/files/model.yaml
# in this repository. Those config files output the SRC_URI's used by Portage.
#
# Update the model.yaml, then run this command from the
# src/platform/dev/contrib directory:
#
#   ./cros_update_firmware --board=%(board_name)s
#
# Verify the changes by running:
#   /build/%(board_name)s/usr/sbin/chromeos-firmwareupdate --manifest
#
# If this works then you can create a CL with your changes, which should include
# the files:
# chromeos-base/chromeos-config-bsp-private/files/model.yaml
# chromeos-base/chromeos-firmware-%(board_name)s/Manifest
# chromeos-base/chromeos-firmware-%(board_name)s/files/srcuris
# chromeos-base/chromeos-firmware-%(board_name)s/chromeos-firmware-%(board_name)s-9999.ebuild
cros-firmware_setup_source
""" % {'board_name': board_name}


def find_file(searchdir, name):
  results = []
  for root, _, files in os.walk(searchdir):
    if name in files:
      results.append(pathlib.Path(root) / name)
  return results


def find_one_file(searchdir, name):
  results = find_file(searchdir, name)
  assert len(results) == 1
  return results.pop()


def sh_getvar(script, varname):
  script = script + ('\necho "${%s}"\n' % varname)
  with tempfile.NamedTemporaryFile('w') as f:
    f.write(script)
    f.flush()
    res = subprocess.run(['sh', f.name], stdout=subprocess.PIPE,
                         check=True, encoding='utf-8')
  return res.stdout.strip() or None


def write_file(fullpath, file_contents, make_ebuild_symlink=False):
  os.makedirs(fullpath.parent, exist_ok=True)
  log('Writing {}...'.format(fullpath))
  with open(fullpath, 'w') as f:
    f.write(file_contents)
  if make_ebuild_symlink:
    if not fullpath.name.endswith('.ebuild'):
      raise ValueError(
          'make_ebuild_symlink specified, but path does not look like an ebuild')
    prefix, _, _ = fullpath.name.rpartition('.')
    linkname = fullpath.parent / '{}-r1.ebuild'.format(prefix)
    log('Creating symlink {} -> {}...'.format(linkname, fullpath))
    os.symlink(fullpath.name, linkname)


def generate_make_defaults(contents):
  contents = make_defaults_search_and_destroy_re.sub('', contents)
  contents += """
# Enable chromeos-config.
USE="${USE} unibuild"
"""
  return contents


class CrosConfig:
  def __init__(self, public_yaml_raw, private_yaml_raw):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as merged_tempfile, \
         tempfile.NamedTemporaryFile(mode='w') as public_yaml_tempfile, \
         tempfile.NamedTemporaryFile(mode='w') as private_yaml_tempfile:
      public_yaml_tempfile.write(public_yaml_raw)
      public_yaml_tempfile.flush()

      private_yaml_tempfile.write(private_yaml_raw)
      private_yaml_tempfile.flush()

      log('Merging and validating config schema...')
      subprocess.run(['cros_config_schema', '-o', merged_tempfile.name,
                      '-m', public_yaml_tempfile.name,
                      private_yaml_tempfile.name], check=True)
      self.merged_yaml = merged_tempfile.name

  def run_host_command(self, *args):
    return subprocess.run(['cros_config_host', '-c', self.merged_yaml]
                          + list(args),
                          check=True, encoding='utf-8',
                          stdout=subprocess.PIPE).stdout


class BoardOverlays:
  FIRMWARE_ATTRS = [
      ('CROS_FIRMWARE_MAIN_IMAGE', 'bcs_main_ro'),
      ('CROS_FIRMWARE_MAIN_RW_IMAGE', 'bcs_main_rw'),
      ('CROS_FIRMWARE_EC_IMAGE', 'bcs_ec'),
      ('CROS_FIRMWARE_PD_IMAGE', 'bcs_pd'),
  ]

  MAKE_DEFAULTS_ATTRS = [
      ('EC_FIRMWARE', 'ec_firmwares'),
      ('PD_FIRMWARE', 'pd_firmwares'),
      ('EC_FIRMWARE_EXTRA', 'ec_firmware_extras'),
      ('FPMCU_FIRMWARE', 'fpmcu_firmware'),
      ('USE', 'use_flags'),
  ]

  def __init__(self, board_name, checkout, mosys_platform):
    self.checkout = checkout
    self.board_name = board_name
    self.mosys_platform = mosys_platform
    self.public_overlay = (checkout / 'src' / 'overlays'
                           / f'overlay-{board_name}')
    log('Public overlay path: {}'.format(self.public_overlay))
    self.private_overlay = (checkout / 'src' / 'private-overlays'
                            / f'overlay-{board_name}-private')
    log('Private overlay path: {}'.format(self.private_overlay))

    assert self.public_overlay.is_dir()
    assert self.private_overlay.is_dir()

    # Find the firmware ebuild
    self.firmware_ebuild_path = find_one_file(
        self.private_overlay, f'chromeos-firmware-{board_name}-9999.ebuild')
    log('Firmware ebuild path: {}'.format(self.firmware_ebuild_path))

    # Read the firmware attrs from it
    for _, attr in self.FIRMWARE_ATTRS:
      setattr(self, attr, None)

    with open(self.firmware_ebuild_path) as f:
      for line in f:
        if '#' in line:
          line, _, _ = line.partition('#')
        line = line.strip()

        for var, attr in self.FIRMWARE_ATTRS:
          if line.startswith('{}='.format(var)):
            _, _, value = line.partition('=')
            value = value.replace('"', '').replace("'", '')
            setattr(self, attr, value)

    # Find make.defaults files
    self.public_make_defaults_file = (
        self.public_overlay / 'profiles' / 'base' / 'make.defaults')
    self.private_make_defaults_file = (
        self.private_overlay / 'profiles' / 'base' / 'make.defaults')

    with open(self.public_make_defaults_file) as f:
      self.public_make_defaults = f.read()
    with open(self.private_make_defaults_file) as f:
      self.private_make_defaults = f.read()

    for var, attr in self.MAKE_DEFAULTS_ATTRS:
      setattr(self, attr, set())
      for script in (self.public_make_defaults, self.private_make_defaults):
        value = sh_getvar(script, var)
        if value:
          for v in value.split():
            getattr(self, attr).add(v)

    if 'whiskers' in self.ec_firmware_extras:
      self.ec_firmware_extras.remove('whiskers')
      self.detachable_base_build_target = 'whiskers'
    else:
      self.detachable_base_build_target = None

    self.ec_build_target = ' '.join(self.ec_firmwares) or None
    self.ec_extras_build_target = sorted(list(self.ec_firmware_extras
                                              | self.pd_firmwares)) or None

  def write_file(self, overlay_flags, path, file_contents,
                 make_ebuild_symlink=False):
    dirs = []
    if overlay_flags & M_PUBLIC:
      dirs += [self.public_overlay]
    if overlay_flags & M_PRIVATE:
      dirs += [self.private_overlay]
    for d in dirs:
      write_file(d / path, file_contents,
                 make_ebuild_symlink=make_ebuild_symlink)


class Dut:
  def __init__(self, hostname, checkout, port=22):
    self.ssh_hostname = hostname

    id_source = checkout / 'chromite' / 'ssh_keys' / 'testing_rsa'
    with open(id_source, 'rb') as f:
      id_contents = f.read()

    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmpfile:
      tmpfile.write(id_contents)
      self.ssh_identity = tmpfile.name

    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
      self.ssh_known_hosts_file = tmpfile.name

    self.ssh_port = port

    # Check connectivity.
    log('Checking SSH connectivity to DUT...')
    self.run_command(['/bin/true'])

  # Linter is unaware that we set check=True in kwargs.
  # pylint: disable=subprocess-run-check
  def run_command(self, argv, *args, **kwargs):
    kwargs.setdefault('check', True)
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('encoding', 'utf-8')
    quoted_argv = [shlex.quote(arg) for arg in argv]
    return subprocess.run(['ssh',
                           '-p', '{}'.format(self.ssh_port),
                           '-i', self.ssh_identity,
                           '-o', 'UserKnownHostsFile={}'.format(
                               self.ssh_known_hosts_file),
                           '-o', 'StrictHostKeyChecking=no',
                           '-o', 'CheckHostIP=no',
                           '-o', 'ConnectTimeout=10',
                           'root@{}'.format(self.ssh_hostname)] + quoted_argv,
                          *args, **kwargs)
  # pylint: enable=subprocess-run-check


class DeviceConfig:
  ATTRS = {
      'brand_code': ['mosys', 'platform', 'brand'],
      'model': ['mosys', 'platform', 'model'],
      'lsb_release': ['cat', '/etc/lsb-release'],
      'smbios_name': ['cat', '/sys/class/dmi/id/product_name'],
      'fdt_compatible_raw': ['cat', '/proc/device-tree/compatible'],
      'arc_build_props': ['cat', '/usr/share/arc/properties/build.prop'],
      'mosys_psu_type': ['mosys', 'psu', 'type'],
      'whitelabel_tag': ['vpd_get_value', 'whitelabel_tag'],
      'customization_id': ['vpd_get_value', 'customization_id'],
      'cras_config_dir': ['sh', '/etc/cras/get_device_config_dir'],
      'internal_ucm_suffix': ['sh', '/etc/cras/get_internal_ucm_suffix'],
      # disgusting, but whatever...
      'powerd_raw':
      ['python3', '-c',
       'import os;'
       'import json;'
       'print(json.dumps('
       '{f.replace("_", "-"): open("/usr/share/power_manager/board_specific/"+f).read().rstrip()'
       ' for f in os.listdir("/usr/share/power_manager/board_specific")}))'],
  }

  @classmethod
  def from_dut(cls, dut):
    slf = cls()
    for attr, cmd in cls.ATTRS.items():
      try:
        log('Running {!r} on DUT...'.format(cmd))
        res = dut.run_command(cmd)
      except subprocess.CalledProcessError:
        setattr(slf, attr, None)
      else:
        setattr(slf, attr, res.stdout.strip())
    return slf

  def __str__(self):
    return 'DeviceConfig({})'.format(
        ', '.join('{}={!r}'.format(attr, getattr(self, attr))
                  for attr in self.ATTRS))

  def lsb_val(self, name, default=None):
    for item in self.lsb_release.splitlines():
      k, _, v = item.partition('=')
      if k == name:
        return v
    return default

  def arc_build_prop(self, name, default=None):
    for line in self.arc_build_props.splitlines():
      if '#' in line:
        line, _, _ = line.partition('#')
      line = line.strip()
      if line.startswith('{}='.format(name)):
        _, _, val = line.partition('=')
        return val
    return default


def genconf_first_api_level(_, overlay):
  if overlay.board_name in ('atlas', 'nocturne'):
    return '28'
  return '25'


def genconf_dt_compatible_match(device, overlay):
  if not device.fdt_compatible_raw:
    return None
  compatible_strings = device.fdt_compatible_raw.strip('\x00').split('\x00')
  compatible_strings.sort(key=lambda s: (s.startswith('google'),
                                         'rev' not in s,
                                         'sku' not in s,
                                         overlay.board_name in s,
                                         -len(s)))
  return compatible_strings[-1]


def genconf_psu_type(device, _):
  if device.mosys_psu_type:
    return device.mosys_psu_type
  devicetype = device.lsb_val('DEVICETYPE')
  if devicetype == 'CHROMEBOOK':
    return 'battery'
  if devicetype in ('CHROMEBIT', 'CHROMEBASE', 'CHROMEBOX'):
    return 'AC_only'
  return None


def genconf_has_backlight(device, _):
  devicetype = device.lsb_val('DEVICETYPE')
  return devicetype not in ('CHROMEBIT', 'CHROMEBOX')


def genconf_fp_board(_, overlay):
  if overlay.fpmcu_firmware:
    return ' '.join(overlay.fpmcu_firmware)
  return None


def genconf_fp_type(_, overlay):
  if 'fp_on_power_button' in overlay.use_flags:
    return 'on-power-button'
  if overlay.fpmcu_firmware:
    return 'stand-alone'
  return None


def genconf_fp_location(_, overlay):
  if overlay.board_name == 'nocturne':
    return 'power-button-top-left'
  return None


def genconf_signature_id(device, _):
  if device.whitelabel_tag:
    return device.whitelabel_tag.upper()
  if device.customization_id:
    return device.customization_id.upper().partition('-')[0]
  return device.model


def genconf_cras_config_dir(device, _):
  prefix = '/etc/cras/'
  if device.cras_config_dir and device.cras_config_dir.startswith(prefix):
    return device.cras_config_dir[len(prefix):]
  if device.cras_config_dir:
    return '../../{}'.format(device.cras_config_dir)
  return None


def genconf_powerd_settings(device, overlay):
  if not device.powerd_raw:
    d = {}
  else:
    d = json.loads(device.powerd_raw)

  # 2-tuples of (use_flag, powerd_option)
  # Source of truth is power_manager ebuild.
  use_flag_settings = [
      ('als', 'has-ambient-light-sensor'),
      ('cras', 'use-cras'),
      ('has_keyboard_backlight', 'has-keyboard-backlight'),
      ('legacy_power_button', 'legacy-power-button'),
      ('mosys_eventlog', 'mosys-eventlog'),
  ]

  for flag, powerd_setting in use_flag_settings:
    if flag in overlay.use_flags:
      d[powerd_setting] = '1'

  return d


def genconf_whitelabel_tag(device, _):
  # Devices with a Customization ID are not compatible with whitelabel
  # tags.
  if device.customization_id:
    return None
  return device.whitelabel_tag or None


def genconf_wallpaper_id(device, overlay):
  wallpapers_dir = (overlay.checkout / 'src' / 'platform' / 'chromeos-assets'
                    / 'wallpaper' / 'large')
  assert wallpapers_dir.is_dir()
  for wallpaper_id in (overlay.board_name, device.model):
    if (wallpapers_dir / f'{wallpaper_id}.jpg').is_file():
      return wallpaper_id
  return None


M_PUBLIC = (1 << 0)
M_PRIVATE = (1 << 1)


genconf_schema = {
    'name': (M_PUBLIC | M_PRIVATE, lambda d, _: d.model),
    'brand-code': (M_PUBLIC, lambda d, _: d.brand_code),
    'arc': {
        'build-properties': {
            'device': (M_PRIVATE, lambda d, _:
                       d.arc_build_prop('ro.product.device')),
            'marketing-name': (M_PRIVATE, lambda d, _:
                               d.arc_build_prop('ro.product.model')),
            'oem': (M_PRIVATE,
                    lambda d, _: d.arc_build_prop('ro.product.brand')),
            'first-api-level': (M_PRIVATE, genconf_first_api_level),
            'metrics-tag': (M_PRIVATE,
                            lambda d, _: d.arc_build_prop('ro.product.board')),
            'product': (M_PRIVATE, lambda d, _:
                        d.arc_build_prop('ro.product.name')),
        },
    },
    'audio': {
        'main': {
            'cras-config-dir': (M_PUBLIC, genconf_cras_config_dir),
            'ucm-suffix': (M_PUBLIC, lambda d, _: d.internal_ucm_suffix),
        },
    },
    'fingerprint': {
        'board': (M_PUBLIC, genconf_fp_board),
        'fingerprint-sensor-type': (M_PUBLIC, genconf_fp_type),
        'sensor-location': (M_PUBLIC, genconf_fp_location),
    },
    'firmware': {
        'image-name': (M_PUBLIC, lambda d, _: d.model),
        'name': (M_PRIVATE, lambda d, _: d.model),
        'bcs-overlay': (M_PRIVATE, lambda _, b:
                        f'overlay-{b.board_name}-private'),
        'ec-ro-image': (M_PRIVATE, lambda _, b: b.bcs_ec),
        'pd-ro-image': (M_PRIVATE, lambda _, b: b.bcs_pd),
        'main-ro-image': (M_PRIVATE, lambda _, b: b.bcs_main_ro),
        'main-rw-image': (M_PRIVATE, lambda _, b: b.bcs_main_rw),
        'build-targets': {
            'base': (M_PUBLIC, lambda _, b: b.detachable_base_build_target),
            'coreboot': (M_PUBLIC, lambda _, b: b.board_name),
            'depthcharge': (M_PUBLIC, lambda _, b: b.board_name),
            'ec': (M_PUBLIC, lambda _, b: b.ec_build_target),
            'ec_extras': (M_PUBLIC, lambda _, b: b.ec_extras_build_target),
        },
    },
    'firmware-signing': {
        'key-id': (M_PRIVATE, lambda d, _: d.model.upper()),
        'signature-id': (M_PRIVATE, genconf_signature_id),
    },
    'hardware-properties': {
        'has-backlight': (M_PUBLIC, genconf_has_backlight),
        'psu-type': (M_PUBLIC, genconf_psu_type),
    },
    'identity': {
        'platform-name': (M_PUBLIC, lambda _, b: b.mosys_platform),
        'smbios-name-match': (M_PUBLIC, lambda d, _: d.smbios_name),
        'device-tree-compatible-match': (M_PUBLIC, genconf_dt_compatible_match),
        'customization-id': (M_PUBLIC, lambda d, _: d.customization_id or None),
        'whitelabel-tag': (M_PUBLIC, genconf_whitelabel_tag),
    },
    'power': (M_PUBLIC, genconf_powerd_settings),
    'wallpaper': (M_PRIVATE, genconf_wallpaper_id),
}


def genconf(schema, device_conf, overlay_conf):

  def qualifies_as_value(v):
    return v is not None and v != {}

  if isinstance(schema, dict):
    pub, priv = {}, {}
    for k, v in schema.items():
      pub_r, priv_r = genconf(v, device_conf, overlay_conf)
      if qualifies_as_value(pub_r):
        pub[k] = pub_r
      if qualifies_as_value(priv_r):
        priv[k] = priv_r
    return pub, priv

  if isinstance(schema, tuple):
    pub, priv = None, None
    flags, func = schema
    value = func(device_conf, overlay_conf)
    if flags & M_PUBLIC:
      pub = value
    if flags & M_PRIVATE:
      priv = value
    return pub, priv


def validate_gs_uri(uri):
  log('Validating {}...'.format(uri))
  subprocess.run(['gsutil', 'stat', uri], check=True, stdout=subprocess.DEVNULL)


def parse_opts(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('--cros-checkout',
                      type=pathlib.Path,
                      default=pathlib.Path(os.getenv('HOME')) / 'trunk',
                      help='Location of the ChromeOS checkout')
  parser.add_argument('--dut', '-d',
                      type=str,
                      required=True,
                      help='Hostname of DUT to use for querying and testing.')
  parser.add_argument('--dut-ssh-port', type=int, default=22,
                      help='SSH port to use on the dut.')
  parser.add_argument('--board', '-b',
                      type=str,
                      required=True,
                      help='Board name to convert.')
  parser.add_argument('--mosys-platform', type=str, required=True)
  parser.add_argument('--dry-run',
                      action='store_true',
                      default=False,
                      help='Dry run')
  return parser.parse_args(argv)


def main(argv):
  opts = parse_opts(argv)

  overlays = BoardOverlays(opts.board, opts.cros_checkout, opts.mosys_platform)
  dut = Dut(opts.dut, opts.cros_checkout, port=opts.dut_ssh_port)

  log('Loading configuration from DUT...')
  dut_config = DeviceConfig.from_dut(dut)
  log('Got configuration: {}'.format(dut_config))

  assert dut_config.lsb_val('CHROMEOS_RELEASE_BOARD') == opts.board
  assert dut_config.lsb_val('CHROMEOS_RELEASE_UNIBUILD', '0') != '1'

  log('Generating chromeos-config values...')
  public_config, private_config = genconf(genconf_schema, dut_config, overlays)

  public_config_yaml = format_yaml(public_config)
  private_config_yaml = format_yaml(private_config)
  log('Got public config: \n{}'.format(public_config_yaml))
  log('Got private config: \n{}'.format(private_config_yaml))

  log('Generating ebuilds...')

  public_vpackage = generate_vpackage(('chromeos-base/chromeos-config-bsp', ))
  private_vpackage = generate_vpackage(
      ('chromeos-base/chromeos-config-bsp',
       'chromeos-base/chromeos-config-bsp-private'))
  log('Got public vpackage: \n{}'.format(public_vpackage))
  log('Got private vpackage: \n{}'.format(private_vpackage))

  public_bsp_ebuild = generate_bsp_ebuild()
  private_bsp_ebuild = generate_bsp_ebuild(private=True)
  log('Got public bsp_ebuild: \n{}'.format(public_bsp_ebuild))
  log('Got private bsp_ebuild: \n{}'.format(private_bsp_ebuild))

  firmware_ebuild = generate_firmware_ebuild(opts.board)
  log('Got firmware ebuild: \n{}'.format(firmware_ebuild))

  public_make_defaults = generate_make_defaults(overlays.public_make_defaults)
  log('Got public make defaults: \n{}'.format(public_make_defaults))
  private_make_defaults = generate_make_defaults(overlays.private_make_defaults)
  log('Got private make defaults: \n{}'.format(private_make_defaults))

  cros_config = CrosConfig(public_config_yaml, private_config_yaml)
  firmware_srcuris = cros_config.run_host_command('get-firmware-uris')
  log('Got firmware URIs: {}'.format(firmware_srcuris))

  log('Validating firmware srcuris...')
  for uri in firmware_srcuris.split():
    validate_gs_uri(uri)

  firmware_srcuris_path = (overlays.firmware_ebuild_path.parent
                           / 'files' / 'srcuris')

  if opts.dry_run:
    return

  overlays.write_file(
      M_PUBLIC, 'chromeos-base/chromeos-config-bsp/files/model.yaml',
      public_config_yaml)
  overlays.write_file(
      M_PRIVATE, 'chromeos-base/chromeos-config-bsp-private/files/model.yaml',
      private_config_yaml)
  overlays.write_file(
      M_PUBLIC, 'virtual/chromeos-config-bsp/chromeos-config-bsp-2.ebuild',
      public_vpackage, make_ebuild_symlink=True)
  overlays.write_file(
      M_PRIVATE, 'virtual/chromeos-config-bsp/chromeos-config-bsp-3.ebuild',
      private_vpackage, make_ebuild_symlink=True)
  overlays.write_file(
      M_PUBLIC,
      'chromeos-base/chromeos-config-bsp/chromeos-config-bsp-9999.ebuild',
      public_bsp_ebuild)
  overlays.write_file(
      M_PRIVATE,
      'chromeos-base/chromeos-config-bsp-private/chromeos-config-bsp-private-9999.ebuild',
      private_bsp_ebuild)
  write_file(overlays.firmware_ebuild_path, firmware_ebuild)
  write_file(firmware_srcuris_path, ''.join('{}\n'.format(uri) for uri in firmware_srcuris.split()))
  write_file(overlays.public_make_defaults_file, public_make_defaults)
  write_file(overlays.private_make_defaults_file, private_make_defaults)


if __name__ == '__main__':
    main(sys.argv[1:])
