# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Upload crash client ID to Issue Tracker by using Issue Tracker API.

Crash client ID and release notes update to the Chromium Issue Tracker system.

"""

import getpass
import httplib
import os
import re
import sys
import urllib


# Create crash client ID and sent to "Consent To Send Stats".
def _get_client_id():
  if not os.path.isfile('/home/chronos/Consent To Send Stats'):
    sys.exit('Please consent to ending stats in Chromium and rerun.')
  else:
    id = open('/home/chronos/Consent To Send Stats', 'r')
    client_id = id.read()
    return client_id

# Get sender's login credentials.
def _get_credential():
  valid_email = False
  while not valid_email:
    email = raw_input('Enter your email : ')
    # Allowing user to use these email domains
    email_domain = re.compile(r'(@chromium.org|@google.com|@gmail.com)$')
    valid_email = (email_domain.search(email))
    if not valid_email:
      print 'Please check email address, and try again'
  pwd = getpass.getpass('Enter your password : ')
  return email, pwd

# Get bug ID corresponding to the crashing report.
def _get_bug_id():
  valid_number = False
  while not valid_number:
    print ('You are about to publish crashing client ID and lsb-release '
           'info to this bug')
    bug_id = raw_input('Enter bug id that you would like to update : ')
    valid_number = re.match(r'^\d+$', bug_id) is not None
  # TODO(tturchetto): Verify bug number is in the chrome OS database.
  return int(bug_id)

# Get lsb_release information from the crashed system.
def _get_lsb_release():
  lsb_info = open('/etc/lsb-release', 'r')
  lsb_release = lsb_info.read()
  return lsb_release

# Get authetication token to access code.google.com
def _get_auth_token(email, pwd):
  google_login_host = 'google.com:443'
  client_login_url = '/accounts/ClientLogin'
  login_values = {
    'Email': email,
    'Passwd': pwd,
    'accountType': 'GOOGLE',
    'service': 'code',
    'source': 'google-crash_uploader-1.0'
  }

  params = urllib.urlencode(login_values)
  headers = {
    'Content-type': 'application/x-www-form-urlencoded',
    'Accept': 'text/plain'
  }

  conn = httplib.HTTPSConnection(google_login_host)
  # Send the request
  conn.request('POST', client_login_url, params, headers)
  response = conn.getresponse()
  response_data = response.read()
  error_code = response.status
  # 200 is expected response status
  if 200 == response.status:
    body = response_data.split('\n')
    for line in body:
      if re.match('Auth=', line):
        token = line.split('=')[1]
        return token
  if 403 == response.status:
    sys.exit('Error: unsupported standard parameter, or authentication'
             'or authorization failed.')

# Create the XML string to be sent as data.
def _create_xml(client_id, lsb_release, email):
  # Create the XML string to be sent as data.
  issue_tracker_xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    ' <entry xmlns="http://www.w3.org/2005/Atom" '
    'xmlns:issues="http://schemas.google.com/projecthosting/issues/2009">\n'
    ' <content type="html">crashing report client ID: "%(client_id)s "\n'
    'lsb_release is\n" %(lsb_release)s"\n'
    ' </content>\n'
    '  <author>\n'
    '    <name>"%(author)s"</name>\n'
    '  </author>\n'
    '  <issues:updates>\n'
    '  </issues:updates>\n'
    '</entry>\n'
  )

  issue_tracker_xml = issue_tracker_xml % {
    'author' : email,
    'client_id' : client_id,
    'lsb_release' : lsb_release
  }
  return issue_tracker_xml

# Comment information to the bug.
def _update_bug(email, bug_id, token, issue_tracker_xml):
  """Updates the bug.
  Args:
    email: An user email to access the Issue Tracker.
    bug_id: Bug ID that user want to update.
    token: Authenticated ClientLogin token to access issue tracker
    issue_tracker_xml: Project hosting on Google Code uses xml entry to updates
    bug
  """

  # Get headers.
  headers = {'Content-type': 'application/atom+xml',
             'Accept': 'text/plain',
             'Authorization': 'GoogleLogin auth=' + token}
  conn = httplib.HTTPConnection('code.google.com:80')
  google_login_host = 'google.com:443'
  issue_update_url = \
    '/feeds/issues/p/chromium-os/issues/%s/comments/full' % ( bug_id )
  # Send the request
  conn.request("POST", issue_update_url, issue_tracker_xml, headers)
  response = conn.getresponse()
  conn.set_debuglevel(1)
  data = response.read()
  conn.close()
  # 201 is expected response status
  if 201 == response.status:
    print ('%s updated bug # %s successfully.' % ( email, bug_id ))
  else:
    print ('Your update is not successful posted on the bug # %s' % ( bug_id ))

def main():
  os.system('clear')
  client_id = _get_client_id()
  (email, password) = _get_credential()
  lsb_release = _get_lsb_release()
  token = _get_auth_token(email, password)
  bug_id = _get_bug_id()
  xml = _create_xml(client_id, lsb_release, email)
  _update_bug(email, bug_id, token, xml)

if __name__ == '__main__':
  main()
