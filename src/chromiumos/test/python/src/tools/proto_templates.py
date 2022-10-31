# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Protos to use CFT with our without chroot.

TODO:
If the chroot is present on the FS, we will use the real protos instead.

If there is no chroot, use the default template.
"""

from typing import Dict, List


def make_testRequest(artifactDir: str, board_key: str, cacheIp: str,
                     cachePort: int, model_key: str, sshAddr: str, port: int,
                     tests: Dict):

  return {
      'artifactDir': artifactDir,
      'primaryDut': {
          'containerMetadataKey': board_key,
          'dut': {
              'cacheServer': {
                  'address': {
                      'address': cacheIp,
                      'port': cachePort
                  }
              },
              'chromeos': {
                  'audio': {},
                  'chameleon': {},
                  'dutModel': {
                      'buildTarget': board_key,
                      'modelName': model_key
                  },
                  'servo': {
                      'present': False
                  },
                  'ssh': {
                      'address': sshAddr,
                      'port': port
                  },
                  'touch': {},
                  'wifi': {
                      'antenna': {
                          'connection': 'OTA'},
                      'environment': 'STANDARD'
                  }
              },
              'id': {
                  'value': sshAddr
              }
          }
      },
      'testSuites': [tests]
    }

def make_prov_request(board_key: str, cacheIp: str, cachePort: int,
                      model_key: str, sshAddr: str, port: int, image_src: str):
  return {
      'devices': [{
          'containerMetadataKey': board_key,
          'dut': {
              'cacheServer': {
                  'address': {
                      'address': cacheIp,
                      'port': cachePort
                  }
              },
              'chromeos': {
                  'audio': {},
                  'chameleon': {},
                  'dutModel': {
                      'buildTarget': board_key,
                      'modelName': model_key
                  },
                  'servo': {
                      'present': False,
                  },
                  'ssh': {
                      'address': sshAddr,
                      'port': port
                  },
                  'touch': {},
                  'wifi': {
                      'antenna': {
                          'connection': 'OTA'
                      },
                      'environment': 'STANDARD'
                  }
              },
              'id': {
                  'value': sshAddr
              }
          },
          'provisionState': {
              'systemImage': {
                  'systemImagePath': {
                      'hostType': 'GS',
                      'path': image_src
                  }
              }
          }
      }]
  }


def make_testFinderRequest(board_key: str, tests: List, tags: List):
  """Take the given tags & tests and convert into testFinder request proto."""
  finder_req = {
      'containerMetadataKey': board_key,
  }
  allTags = []
  if tags:
    allTags.extend(makeTags(tags))
  if tests:
    t = makeTests(tests)
    allTags.extend([t])
  finder_req['testSuites'] = allTags  # type: ignore
  return finder_req


def makeTags(tags: List):
  temps = []
  for tag in tags:
    temps.append({
        'testCaseTagCriteria': {
            'tags': [tag]
        }
    })
  return temps


def makeTests(tests: List):
  temps = []
  for test in tests:
    temps.append({'value': test})

  return {
      'testCaseIds': {
          'testCaseIds': temps
      }
  }
