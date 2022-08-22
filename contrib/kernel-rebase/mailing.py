# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Disable pylint noise
# pylint: disable=W0621, E0401, C0415, W1632

"""Sends triage reports"""

import smtplib
import pickle
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import rebase_target, rebase_baseline_branch

cred_error = """\
ERROR: cred.py file not found. Create it in and initialize login, passw
variables within, for example:
login = "you@gmail.com"
passw = "your application password"
It'll work only for GMail, anyway.
"""

html_header = """<html>
  <head></head>
  <body><pre>
"""
html_footer = """</pre>
</body>
</html>
"""

email_text = """\
This is an automatic notification about %s -> merge/continuous/chromeos-kernelupstream-%s
uprev status.
Commits in "handled automatically" column were either dropped (due to revert or upstream)
or resolved using preexisting resolutions.
Commits counted as "need manual resolution" were skipped for the purpose of triage.

topic          | commits overall | handled automatically | need manual resolution*| build
---------------+-----------------+-----------------------+------------------------+------
"""

upstream_prefix = """\
upstreaming stats:
 category  | fromlist | fromgit
-----------+----------+--------
"""

email_subject = '%s -> %s: %d/%d commits need manual resolution'

mailing_from = 'from@example.com'
recip_limited = ['recip1@example.com', 'recip2@example.com']
recip_all = [
    'recip1@example.com',
    'recip2@example.com',
    'recip3@example.com',
    'recip4@example.com']


class Mailing:
    """Mailing class"""

    def __init__(self, rebase_base, rebase_target):
        """Initializes class members"""

        self.rebase_base = rebase_base
        self.rebase_target = rebase_target
        self.server = None

    def build_mail(
            self,
            topic_stats,
            upstream_stats,
            total_stats,
            topic_errors):
        """Formats statistics into an email"""

        mail = email_text % (self.rebase_base, self.rebase_target[1:])
        stats = [0, 0, 0, 0]
        for topic in topic_stats:
            data = topic_stats[topic]
            overall = data[0]
            auto = data[1]
            manual = data[2]
            fixup_manual = data[3]
            stats[0] += overall
            stats[1] += auto
            stats[2] += manual
            stats[3] += fixup_manual
            if data[4]:
                build = 'OK'
            else:
                build = 'FAIL'
            val = f'{manual}+{fixup_manual}'
            mail += f'{topic:14} | {overall:15d} | {auto:21d} | {val:>22s} | {build}\n'

        topic = 'ALL'
        build = 'ON HOLD'
        mail += '-' * len(email_text.split('\n')[6])
        mail += '\n'
        val = f'{stats[2]}+{stats[3]}'
        mail += f'{topic:14} | {stats[0]:15d} | {stats[1]:21d} | {val:>22s} | {build}\n'
        mail += '\n'

        mail += upstream_prefix
        fromlist = total_stats['fromlist']
        fromgit = total_stats['fromgit']
        mail += f'total      | {fromlist:8} | {fromgit:7}\n'
        fromlist = upstream_stats['fromlist']
        fromgit = upstream_stats['fromgit']
        mail += f'upstreamed | {fromlist:8} | {fromgit:7}\n\n'

        for topic in topic_errors:
            mail += 'Branch %s failed to build due to:\n' % topic
            mail += topic_errors[topic]
            mail += '\n\n'

        mail += '* - is a number of commmits+fixups which need manual resolution'
        mail += '\n'

        return (mail, stats)

    def send_mail(self, subject, mail, recipients):
        """Send mail"""

        try:
            from cred import login, passw
        except: # pylint: disable=bare-except
            print(cred_error)
            sys.exit()
        self.server = smtplib.SMTP('smtp.gmail.com', 587)
        self.server.starttls()
        self.server.login(login, passw)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mailing_from
        msg['To'] = ', '.join(recipients)
        part1 = MIMEText(
            'This message should be viewed in HTML. Check your client.',
            'plain')
        part2 = MIMEText(html_header + mail + html_footer, 'html')
        msg.attach(part1)
        msg.attach(part2)
        self.server.send_message(msg)

    def notify(self, topic_stats, upstream_stats, total_stats, topic_errors):
        """Preview and send report"""

        mail, stats = self.build_mail(
            topic_stats, upstream_stats, total_stats, topic_errors)
        subject = email_subject % (
            self.rebase_base, self.rebase_target, stats[2], stats[0])
        print(mail)
        ans = input('Send? [y/n] ')
        if ans == 'y':
            # Send out to limited audience first
            self.send_mail(subject, mail, recip_limited)
        ans = input('Resend to all? [y/n] ')
        if ans == 'y':
            # Send out to all
            self.send_mail(subject, mail, recip_all)


def load_and_notify():
    """Creates a report, shows preview and sends it if ok"""

    m = Mailing(rebase_baseline_branch, rebase_target)
    topic_stats = pickle.load(open('topic_stats.bin', 'rb'))
    topic_stderr = pickle.load(open('topic_stderr.bin', 'rb'))
    upstream_stats = pickle.load(open('upstream_stats.bin', 'rb'))
    total_stats = pickle.load(open('total_stats.bin', 'rb'))
    m.notify(topic_stats, upstream_stats, total_stats, topic_stderr)
