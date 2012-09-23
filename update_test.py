#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from xml.dom import minidom
import sys
import threading
import urllib2


UPDATE_BLOB="""\
<?xml version="1.0" encoding="UTF-8"?>
<o:gupdate
  xmlns:o="http://www.google.com/update2/request"
  version="MementoSoftwareUpdate-0.1.0.0"
  protocol="2.0"
  machineid="{1B0A13AC-7004-638C-3CA6-EC082E8F5DE9}"
  ismachine="0"
  userid="{bogus}">
<o:os version="Memento"
   platform="memento"
   sp="ForcedUpdate_i686">
</o:os>
<o:app appid="{87efface-864d-49a5-9bb3-4b050a7c227a}"
   version="ForcedUpdate"
   lang="en-us"
   brand="GGLG"
   track="developer-build"
   board="x86-generic">
<o:ping active="0"></o:ping>
<o:updatecheck></o:updatecheck>
</o:app>
</o:gupdate>
"""

UPDATE_URL = 'http://localhost:8080/update/'

def do_ping():
  update_ping = urllib2.Request(UPDATE_URL, update_blob)
  update_ping.add_header('Content-Type', 'text/xml')
  print urllib2.urlopen(update_ping).read()
  #TODO assert noupdate

def do_version_ping():
  url = UPDATE_URL + 'LATEST'
  update_ping = urllib2.Request(url, UPDATE_BLOB)
  update_ping.add_header('Content-Type', 'text/xml')
  response = urllib2.urlopen(update_ping).read()
  assert _verify_response(response), 'couldn\'t fetch update file'
  print 'Successfully pinged updateserver.'

def do_badversion_ping():
  url = UPDATE_URL + 'BADVERSION'
  update_ping = urllib2.Request(url, UPDATE_BLOB)
  update_ping.add_header('Content-Type', 'text/xml')
  response = urllib2.urlopen(update_ping).read()
  assert ('noupdate' in response)
  print 'requesting bogus version returns noupdate.'

def _verify_download(url, content_length):
  # Eventually, verify something about the update. For now,
  # sanity-check its size.
  f = urllib2.urlopen(url)
  data = f.read(1024 * 1024)
  length = len(data)
  while data:
    data = f.read(1024 * 1024)
    length += len(data)
  assert content_length == length
  print 'Got a valid download.'
  return True

def _verify_response(data):
  update_dom = minidom.parseString(data)
  print data
  root = update_dom.firstChild
  update_info = root.getElementsByTagName('updatecheck')[0]
  update_url = update_info.getAttribute('codebase')
  hash = update_info.getAttribute('hash')
  head_request = urllib2.Request(update_url)
  head_request.get_method = lambda: 'HEAD'
  try:
    fd = urllib2.urlopen(head_request)
  except urllib2.HTTPError, e:
    # HTTP error
    print 'FAILED: unable to retrieve %s\n\t%s' % (update_url, e)
    length = 0
  else:
    # HTTP succeeded
    length = int(fd.headers.getheaders('Content-Length')[0])
  finally:
    fd.close()
    return (length > 0)

def test(num_clients):
  # Fake some concurrent requests for each autoupdate operation.
  for clients in range(num_clients):
    for op in (do_version_ping, do_badversion_ping):
      t = threading.Thread(target=op)
      t.start()

if __name__ == '__main__':
  if len(sys.argv) > 1:
    num_clients = int(sys.argv[1])
  else:
    num_clients = 1
  test(num_clients)
