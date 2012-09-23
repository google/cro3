#!/usr/bin/python

# Copyright (c) 2009-2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script updates given firmware in shellball and puts in an image.

This scripts mounts given image and copies chromeos-firmwareupdate file. Then
extracts chromeos-firmwareupdater and replaces given bios.bin in
chromeos-firmwareupdater, re-packs the file and enables firmare update.
At the end it unmounts the image.

This is useful for test team to test new firmware/coreboot.

Syntax:
  update_firmware_image.py --imagedir <path to image> --image <image name>
  --bios <path to bios>
  e.g. update_firmware_image.py --imagedir /home/$USER/src/images/
                                --image chromiumos_test_image.bin
                                --bios /home/$USER/src/bios/bios.bin
"""

#__author__ = 'rchenna@google.com (Rajesh Chenna)'

# TODO(garnold) deprecated module, switch to using subprocess.
import commands
import logging
import optparse
import os
import re
import sys


# Constants
dev_keys = '$HOME/trunk/src/platform/vboot_reference/tests/devkeys'
mount_gpt_image = '$HOME/trunk/src/scripts/mount_gpt_image.sh'
image_signing_dir = ('$HOME/trunk/src/platform/vboot_reference/scripts/'
                       'image_signing')

def main():

  parser = optparse.OptionParser()
  parser.add_option('-b', '--bios', help='bios name including path')
  parser.add_option('-d', '--imagedir', help='image directory')
  parser.add_option('-i', '--image', help='image name')

  (options, args) = parser.parse_args()
  # Checking whether running inside chroot or not.
  if not os.path.exists('/etc/debian_chroot'):
    logging.fatal("Make sure you are inside chroot")
    sys.exit(0)
  # Conditions to check all arguments.
  if not all([options.bios,
              options.imagedir,
              options.image]):
    logging.fatal('Missing arguments.')
    logging.fatal('Please provide bios, imagedir and image')
    sys.exit(0)

  # Verify bios.bin is passing.
  #If not, copy the supplied bios to bios.bin.
  if 'bios.bin' not in options.bios:
    os.system('cp %s %s/bios.bin' %(options.bios,
                                    options.bios[:options.bios.rfind('/')]))
  # Step1: Mount the image.
  os.system('sudo %s --from %s --image %s'
            % (mount_gpt_image, options.imagedir,
               options.image))

  # Step2: copy shellball.
  os.system('sudo cp /tmp/m/usr/sbin/chromeos-firmwareupdate /tmp/')
  # Step3: Extract shellball.
  extract = commands.getoutput('sudo /tmp/chromeos-firmwareupdate '
                               '--sb_extract')
  extract_dir = re.match('Extracting to: (.+)', extract)
  # Step4: copy bios.bin to extracted directory.
  os.system('sudo cp %s/bios.bin %s/'
            %(options.bios[:options.bios.rfind('/')], extract_dir.group(1)))
  # Step5: repack shellball.
  os.system('sudo /tmp/chromeos-firmwareupdate --sb_repack %s'
            %(extract_dir.group(1)))
  # Step6: copy shellball back to /tmp/m location.
  os.system('sudo mv /tmp/chromeos-firmwareupdate /tmp/m/usr/sbin/')
  # Step7: Unmount the image.
  os.system('%s -u' %mount_gpt_image)
  # Step 8: enable firmware update.
  os.system('sudo %s/tag_image.sh --from=%s/%s --update_firmware=1'
            %(image_signing_dir,
              options.imagedir,
              options.image))
  # Step 9: Re-sign the image.
  os.system('sudo %s/sign_official_build.sh usb %s/%s %s %s/resigned_%s'
            %(image_signing_dir,
              options.imagedir,
              options.image,
              dev_keys,
              options.imagedir,
              options.image))

if __name__ == '__main__':
  main()
