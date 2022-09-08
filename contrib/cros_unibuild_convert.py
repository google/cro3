#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
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
import hashlib
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
      """Copyright {} The ChromiumOS Authors
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


def format_yaml(config, device_configs, used_vars):
  conf_str = yaml.dump(config, indent=2, default_flow_style=False)
  out = gen_cros_copyright()
  out += """
device-config: &device_config\n"""
  out += prepend_all_lines(conf_str, '  ')
  out += """
chromeos:
  devices:\n"""
  for dev in device_configs:
    out += "    - "
    for var in used_vars:
      out += "${}: {}\n".format(var, getattr(dev, var))
      out += "      "
    out += """skus:
        - config: *device_config\n"""
  return out


def generate_bsp_ebuild(private=False):
  return gen_cros_copyright() + """
EAPI=7

# cros_workon applies only to ebuild and files directory. Use the
# canonical empty project.
CROS_WORKON_PROJECT="chromiumos/infra/build/empty-project"
CROS_WORKON_LOCALNAME="platform/empty-project"

inherit cros-workon cros-unibuild

DESCRIPTION="ChromeOS model configuration"
HOMEPAGE="https://chromium.googlesource.com/chromiumos/platform2/+/HEAD/chromeos-config/README.md"

LICENSE="BSD-Google"
SLOT="0"
KEYWORDS="~*"

src_install() {
\tinstall%(maybe_private)s_model_files
}
""" % {'maybe_private': '_private' if private else ''}


def generate_firmware_ebuild(board_name):
  return gen_cros_copyright() + """
EAPI=7
CROS_WORKON_LOCALNAME="platform/firmware"
CROS_WORKON_PROJECT="chromiumos/platform/firmware"

inherit cros-workon cros-firmware cros-unibuild

DESCRIPTION="Chrome OS Firmware (%(board_name)s)"
HOMEPAGE="http://src.chromium.org"
LICENSE="BSD-Google"
SLOT="0"
KEYWORDS="~*"

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


def write_file(fullpath, file_contents):
  os.makedirs(fullpath.parent, exist_ok=True)
  log('Writing {}...'.format(fullpath))
  with open(fullpath, 'w') as f:
    f.write(file_contents)


def generate_make_defaults(contents, private=False):
  contents = make_defaults_search_and_destroy_re.sub('', contents)
  bsp_use_flag = 'has_chromeos_config_bsp'
  if private:
    bsp_use_flag += '_private'
  contents += """
# Enable chromeos-config.
USE="${USE} unibuild %(bsp_use_flag)s"
""" % dict(bsp_use_flag=bsp_use_flag)
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
      ('USE', 'use_flags'),
  ]

  def __init__(self, board_name, checkout):
    self.checkout = checkout
    self.board_name = board_name
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

  def write_file(self, overlay_flags, path, file_contents):
    dirs = []
    if overlay_flags & M_PUBLIC:
      dirs += [self.public_overlay]
    if overlay_flags & M_PRIVATE:
      dirs += [self.private_overlay]
    for d in dirs:
      write_file(d / path, file_contents)


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
      'brand_code': ['cros_config', '/', 'brand-code'],
      'model': ['cros_config', '/', 'name'],
      'mosys_platform': ['mosys', 'platform', 'name'],
      'ro_fwid': ['crossystem', 'ro_fwid'],
      'arc_build_props': ['cat', '/usr/share/arc/properties/build.prop'],
      'customization_id': ['vpd_get_value', 'customization_id'],
      'vpd_model_name': ['vpd_get_value', 'model_name'],
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
  def attrs_version(cls):
    """A unique string that should change when ATTRS changes."""
    jsonified = json.dumps(cls.ATTRS)
    return hashlib.sha224(jsonified.encode('utf-8')).hexdigest()

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
    slf.origin = f'[{dut.ssh_hostname}]:{dut.ssh_port}'
    return slf

  @classmethod
  def from_dict(cls, data):
    """Load a DUT from a dictionary of saved attributes."""
    slf = cls()
    for attr, value in data.items():
      setattr(slf, attr, value)
    return slf

  def to_dict(self):
    """Convert to a dictionary that from_dict could be used with."""
    result = {}
    for attr in self.ATTRS:
      result[attr] = getattr(self, attr)
    result['origin'] = self.origin
    return result

  def __str__(self):
    return 'DeviceConfig({})'.format(
        ', '.join('{}={!r}'.format(attr, getattr(self, attr))
                  for attr in self.ATTRS))

  def arc_build_prop(self, name, default=None):
    for line in self.arc_build_props.splitlines():
      if '#' in line:
        line, _, _ = line.partition('#')
      line = line.strip()
      if line.startswith('{}='.format(name)):
        _, _, val = line.partition('=')
        return val
    return default

  @property
  def frid(self):
    frid = self.ro_fwid or ''
    frid, _, _ = frid.partition('.')
    return frid

  @property
  def loem(self):
    loem = ''
    if self.customization_id:
      loem, _, _ = self.customization_id.partition('-')
    return loem

  @property
  def chassis(self):
    return self.model.upper()

  @property
  def marketing_name(self):
    return self.vpd_model_name or self.arc_build_prop('ro.product.brand')


def genconf_signature_id(device, _):
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
  ]

  for flag, powerd_setting in use_flag_settings:
    if flag in overlay.use_flags:
      d[powerd_setting] = '1'

  return d


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
            'marketing-name': (M_PRIVATE, lambda d, _: d.marketing_name),
            'oem': (M_PRIVATE,
                    lambda d, _: d.arc_build_prop('ro.product.brand')),
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
            'bmpblk': (M_PUBLIC, lambda _, b: b.board_name),
            'coreboot': (M_PUBLIC, lambda _, b: b.board_name),
            'depthcharge': (M_PUBLIC, lambda _, b: b.board_name),
            'ec': (M_PUBLIC, lambda _, b: b.ec_build_target),
            'ec-extras': (M_PUBLIC, lambda _, b: b.ec_extras_build_target),
            'libpayload': (M_PUBLIC, lambda _, b: b.board_name),
        },
    },
    'firmware-signing': {
        'key-id': (M_PRIVATE, lambda d, _: d.model.upper()),
        'signature-id': (M_PRIVATE, genconf_signature_id),
    },
    'hardware-properties': {
        'form-factor': (M_PUBLIC, lambda d, b: 'CHROMEBOOK'),
        'has-backlight': (M_PUBLIC, lambda d, b: True),
        'psu-type': (M_PUBLIC, lambda d, b: 'battery'),
    },
    'identity': {
        'platform-name': (M_PUBLIC, lambda d, _: d.mosys_platform),
        'frid': (M_PUBLIC, lambda d, _: d.frid),
        'customization-id': (M_PUBLIC, lambda d, _: d.customization_id or None),
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


def unify_configs(dev_configs, configs):
  """Merge multiple configs together by replacing device config
  attributes with templates recognized by cros_config_schema (in the
  format {{$device_config_attribute}}).

  Args:
    dev_configs: a list of DeviceConfig to operate on.
    configs: the list of cros_config json-like configs to merge.

  Returns:
    A two tuple of (unified_config, vars_used).
  """
  configs = list(configs)

  def configs_are_unified():
    return all(configs[0] == cfg for cfg in configs[1:])

  if configs_are_unified():
    return configs[0], set()

  if isinstance(configs[0], str):
    replace_vars = ('model', 'loem', 'chassis', 'brand_code', 'frid',
                    'marketing_name')
    vars_used = set()
    for var in replace_vars:
      for i in range(len(configs)):
        device_config = dev_configs[i]
        value = getattr(device_config, var)
        if not value:
          break
        old_config_value = configs[i]
        configs[i] = configs[i].replace(value, '{{$%s}}' % var)
        if i == 0 and configs[i] == old_config_value:
          break
        vars_used.add(var)
      if configs_are_unified():
        return configs[0], vars_used

  if isinstance(configs[0], dict):
    result = {}
    used_vars = set()
    for key in configs[0]:
      item_result, item_used_vars = unify_configs(
          dev_configs, [cfg[key] for cfg in configs]
      )
      result[key] = item_result
      used_vars |= item_used_vars

    return result, used_vars

  raise ValueError("Can't unify configs: {!r}".format(configs))


def validate_gs_uri(uri):
  log('Validating {}...'.format(uri))
  subprocess.run(['gsutil', 'stat', uri], check=True, stdout=subprocess.DEVNULL)


def load_duts(dut_string, cros_checkout):
  """Generate DeviceConfigs for each DUT or file specification.

  Args:
    dut_string: Either a file path to a DUT JSON, or host[:port] of a
        DUT to SSH into.
    cros_checkout: Path to a chromiumos checkout.

  Yields:
    DeviceConfigs generated by SSH'ing into the DUT, or from loading a file.
  """
  dut_file_path = pathlib.Path(dut_string)
  if dut_file_path.is_file():
    file_json = json.loads(dut_file_path.read_text())
    if file_json['version'] != DeviceConfig.attrs_version():
      raise RuntimeError(
          f'The DUT file {dut_string} was generated with an older (or newer?) '
          f'version of this script, and cannot be interpreted.'
      )
    for dut_json in file_json['duts']:
      yield DeviceConfig.from_dict(dut_json)
    return

  if dut_string[0] == '[':
    endpos = dut_string.find(']')
    hostname = dut_string[1:endpos]
    _, _, port = dut_string[endpos:-1].partition(':')
  else:
    hostname, _, port = dut_string.partition(':')

  if port:
    port = int(port)
  else:
    port = 22
  dut = Dut(hostname, cros_checkout, port=port)
  yield DeviceConfig.from_dut(dut)


def parse_opts(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument('--cros-checkout',
                      type=pathlib.Path,
                      default=pathlib.Path(os.getenv('HOME')) / 'chromiumos',
                      help='Location of the ChromeOS checkout')
  parser.add_argument(
      '--dut-data-out',
      type=pathlib.Path,
      help=(
          'Path to a file that probed DUT data can be saved to for later use.  '
          'Note that providing this will skip the unibuild conversion.  You '
          'will need to call this script again passing the output file as a '
          '-d/--dut argument.'
      ),
  )
  parser.add_argument('--dut', '-d',
                      action='append',
                      dest='duts',
                      help=('Hostname of DUT(s) to use for querying. '
                            'Note: multiple duts can be passed, which is useful'
                            ' for converting a zerg board like hana or lars.'))
  parser.add_argument('--board', '-b',
                      type=str,
                      required=True,
                      help='Board name to convert.')
  parser.add_argument('--dry-run',
                      action='store_true',
                      default=False,
                      help='Dry run')
  return parser.parse_args(argv)


def main(argv):
  opts = parse_opts(argv)

  dut_configs = []
  for dut_string in opts.duts:
    dut_configs.extend(load_duts(dut_string, cros_checkout=opts.cros_checkout))

  if opts.dut_data_out:
    log(f'Writing DUT data to output file: {opts.dut_data_out}')
    dut_data = {
        'version': DeviceConfig.attrs_version(),
        'duts': [device.to_dict() for device in dut_configs],
    }
    file_contents = json.dumps(dut_data, indent=2)
    if not file_contents.endswith('\n'):
      file_contents += '\n'
    opts.dut_data_out.write_text(file_contents)
    log(f'To do the migration, run me again with --dut={opts.dut_data_out}')
    return

  overlays = BoardOverlays(opts.board, opts.cros_checkout)

  dut_public_configs = []
  dut_private_configs = []
  for dut in dut_configs:
    log(f'Generating chromeos-config values for {dut.origin}...')
    dut_public_config, dut_private_config = genconf(
        genconf_schema, dut, overlays)
    log("PUBLIC={!r}".format(dut_public_config))
    log("PRIVATE={!r}".format(dut_private_config))
    dut_public_configs.append(dut_public_config)
    dut_private_configs.append(dut_private_config)

  log('Unifying public configs...')
  public_config, public_config_vars = unify_configs(
      dut_configs, dut_public_configs)

  log('Unifying private configs...')
  private_config, private_config_vars = unify_configs(
      dut_configs, dut_private_configs)

  public_config_yaml = format_yaml(
      public_config, dut_configs, public_config_vars
  )
  log('Got public config: \n{}'.format(public_config_yaml))
  private_config_yaml = format_yaml(
      private_config, dut_configs, private_config_vars
  )
  log('Got private config: \n{}'.format(private_config_yaml))

  log('Generating ebuilds...')

  public_bsp_ebuild = generate_bsp_ebuild()
  private_bsp_ebuild = generate_bsp_ebuild(private=True)
  log('Got public bsp_ebuild: \n{}'.format(public_bsp_ebuild))
  log('Got private bsp_ebuild: \n{}'.format(private_bsp_ebuild))

  firmware_ebuild = generate_firmware_ebuild(opts.board)
  log('Got firmware ebuild: \n{}'.format(firmware_ebuild))

  public_make_defaults = generate_make_defaults(overlays.public_make_defaults)
  log('Got public make defaults: \n{}'.format(public_make_defaults))
  private_make_defaults = generate_make_defaults(
      overlays.private_make_defaults,
      private=True,
  )
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
      M_PUBLIC,
      'chromeos-base/chromeos-config-bsp/chromeos-config-bsp-9999.ebuild',
      public_bsp_ebuild)
  overlays.write_file(
      M_PRIVATE,
      'chromeos-base/chromeos-config-bsp-private/chromeos-config-bsp-private-9999.ebuild',
      private_bsp_ebuild)
  overlays.write_file(
      M_PUBLIC,
      'chromeos-base/chromeos-config-bsp/OWNERS',
      'include chromiumos/owners:v1:/platform/OWNERS.cros_config\n',
  )
  overlays.write_file(
      M_PRIVATE,
      'chromeos-base/chromeos-config-bsp-private/OWNERS',
      'include chromeos/owners:v1:/platform/OWNERS.cros_config\n',
  )
  write_file(overlays.firmware_ebuild_path, firmware_ebuild)
  write_file(firmware_srcuris_path, ''.join('{}\n'.format(uri) for uri in firmware_srcuris.split()))
  write_file(overlays.public_make_defaults_file, public_make_defaults)
  write_file(overlays.private_make_defaults_file, private_make_defaults)


if __name__ == '__main__':
    main(sys.argv[1:])
