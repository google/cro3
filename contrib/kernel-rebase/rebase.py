#!/usr/bin/env python3

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is contrib-quality code: not all functions/classes are
# documented.
# pylint: disable=import-error
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
# pylint: disable=import-outside-toplevel
# pylint: disable=missing-function-docstring
# pylint: disable=input-builtin
# pylint: disable=redefined-outer-name
# pylint: disable=banned-string-format-function

"""Automatic rebase

This script automates much of the continuous rebase, which is a process
designed for carrying patches from the `living` Chrome OS branch (latest LTS)
to newer upstream kernels.

See go/cont-rebase for details
"""

from datetime import datetime
import importlib
import multiprocessing
from multiprocessing import Manager
import os
import pickle
import re
import sqlite3
import sys

from common import executor_io
from common import rebasedb
from githelpers import *
from logging_console import LoggingConsole

# the import is not used directly, but instead intended to be used in the interactive mode
from mailing import load_and_notify  # pylint: disable=unused-import
import rebase_config
import sh

from config import *


def call_hook(sha, hook_type):
    if '*' in rebase_config.commit_hooks:
        entry = rebase_config.commit_hooks['*']
        if hook_type in entry['types']:
            hook = entry['hook']
            hook(sha, hook_type)
    if sha in rebase_config.commit_hooks:
        entry = rebase_config.commit_hooks[sha]
        if hook_type in entry['types']:
            hook = entry['hook']
            hook(sha, hook_type)

def do_on_cros_sdk_impl(command, ret_by_arg=None):
    result = {'exit_code': None, 'output': None, 'error_line': None}
    os.system("echo '" + command + "' > " + executor_io + '/commands &')
    os.system('cat ' + executor_io + '/output > output.log')
    try:
        with open(executor_io + '/last_exit') as last_exit:
            ec = last_exit.read()
        result['exit_code'] = int(ec[:-1])
    except: # pylint: disable=bare-except
        print('failed to read a valid exit code from last_exit')
        return {}
    try:
        with open('output.log') as output:
            result['output'] = output.read()
        lines = result['output'].splitlines()
        for n in range(len(lines)): # pylint: disable=C0200
            if 'Error 1' in lines[n]:
                result['error_line'] = n + 1
                break
    except: # pylint: disable=bare-except
        print('failed to read output.log')
    if ret_by_arg is not None:
        for k, v in result.items():
            ret_by_arg[k] = v
    return result


def do_on_cros_sdk(command, timeout_s=None):
    if timeout_s is not None:
        manager = Manager()
        result = {}
        shared_dict = manager.dict()
        p = multiprocessing.Process(
            target=do_on_cros_sdk_impl, args=(
                command, shared_dict,))
        p.start()
        p.join(timeout_s)
        if p.is_alive():
            print('execution timed out, is executor.sh running in cros_sdk?')
            p.terminate()
            p.join()
        else:
            for k, v in shared_dict.items():
                result[k] = v
        return result
    return do_on_cros_sdk_impl(command)

def normalize():
    kernelupstream_branch = branch_name('kernelupstream', rebase_target, None)
    print(f'Checking out {kernelupstream_branch}')
    checkout('kernel-upstream', kernelupstream_branch)

    def in_linux_chrome(command):
        return 'cd ./data/repositories/linux-chrome/; ' + command
    def in_configs(command):
        return 'cd ./data/repositories/linux-chrome/CONFIGS; ' + command
    def in_knext(command):
        return 'cd kernel-upstream; ' + command

    configs = [
        (
            'arm64-chromiumos-arm64.flavour.config',
            'arm64/chromiumos-arm64.flavour.config'
        ), (
            'arm64-chromiumos-mediatek.flavour.config',
            'arm64/chromiumos-mediatek.flavour.config'
        ), (
            'arm64-chromiumos-qualcomm.flavour.config',
            'arm64/chromiumos-qualcomm.flavour.config'
        ), (
            'arm64-chromiumos-rockchip64.flavour.config',
            'arm64/chromiumos-rockchip64.flavour.config'
        ), (
            'armel-chromiumos-arm.flavour.config',
            'armel/chromiumos-arm.flavour.config'
        ), (
            'armel-chromiumos-rockchip.flavour.config',
            'armel/chromiumos-rockchip.flavour.config'
        ), (
            'x86_64-chromeos-amd-stoneyridge.flavour.config',
            'x86_64/chromeos-amd-stoneyridge.flavour.config'
        ), (
            'x86_64-chromeos-intel-denverton.flavour.config',
            'x86_64/chromeos-intel-denverton.flavour.config'
        ), (
            'x86_64-chromeos-intel-pineview.flavour.config',
            'x86_64/chromeos-intel-pineview.flavour.config'
        ), (
            'x86_64-chromiumos-x86_64.flavour.config',
            'x86_64/chromiumos-x86_64.flavour.config'
        )
    ]
    iwls = [
        'CONFIG_IWLWIFI=m',
        'CONFIG_IWLDVM=m',
        'CONFIG_IWLMVM=m',
        'CONFIG_IWLWIFI_DEBUGFS=y'
    ]
    iwl_fix_configs = [
        'chromeos/config/chromeos/x86_64/chromeos-intel-denverton.flavour.config',
        'chromeos/config/chromeos/x86_64/chromeos-intel-pineview.flavour.config'
    ]

    genconfig = in_linux_chrome('chromeos/scripts/kernelconfig genconfig 2>&1')

    commands = [
        in_configs('cp ' + config[0] + ' ../../../../kernel-upstream/chromeos/config/chromeos/' + config[1] + ' 2>&1')  # pylint: disable=C0301
        for config in configs
    ] + [
        in_knext('echo "' + iwl + '" >> ' + file)
        for iwl in iwls
        for file in iwl_fix_configs
    ] + [
        in_knext('chromeos/scripts/kernelconfig olddefconfig 2>&1'),
        in_knext('git add -A 2>&1'),
        in_knext('git commit -m "kernel-rebase: normalization [autogenerated]" 2>&1')
    ]

    while True:
        print('genconfig')
        res = do_on_cros_sdk(genconfig)
        output = res['output']
        ec = res['exit_code']
        print(output, end='')

        if ec != 0:
            if 'this assembler is not supported' in output:
                print('This failure might be caused be the lack of commit e749464a877aa:')
                print('"CHROMIUM: kernelconfig sets CROSS_COMPILE"')
            return
        break

    for command in commands:
        print('executing', command)
        res = do_on_cros_sdk(command)
        output = res['output']
        ec = res['exit_code']

        print(output, end='')
        if ec != 0:
            print('exit code:', ec)
            return

def verify_build(sha):
    assert not is_dirty(
        'kernel-upstream'), "There's a local diff in kernel repo. Clean it to continue."
    if sha is not None:
        checkout('kernel-upstream', sha)
    return do_on_cros_sdk(
        'emerge-' +
        rebase_config.verify_board +
        ' --color n -B ' + rebase_config.verify_package)

class Rebaser:
    """Keeps all automatic rebase data"""

    def __init__(self, branch_prefix='test'):
        assert not is_dirty(
            'kernel-upstream'), "There's a local diff in kernel repo. Clean it to continue."

        self.db = sqlite3.connect(rebasedb)
        self.cur = self.db.cursor()
        self.branch_prefix = branch_prefix

        # Create topic dict (name->gid)
        self.topics = {}
        self.cur.execute('select topic, name from topics')
        t = self.cur.fetchall()
        for gid, name in t:
            self.topics[name] = gid
        print('Topic dict: ', self.topics)

        self.upstreamed = {
            'upstream': 0,
            'fromlist': 0,
            'fromgit': 0,
            'backport': 0}
        self.total = {
            'upstream': 0,
            'fromlist': 0,
            'fromgit': 0,
            'backport': 0}
        self.cur.execute('select subject, reason from commits')
        t = self.cur.fetchall()
        for subject, reason in t:
            subject_l = subject.lower()
            if 'fromlist:' in subject_l:
                self.total['fromlist'] += 1
                if 'upstream' in reason:
                    self.upstreamed['fromlist'] += 1
            if 'fromgit:' in subject_l:
                self.total['fromgit'] += 1
                if 'upstream' in reason:
                    self.upstreamed['fromgit'] += 1
            if 'upstream:' in subject_l:
                self.total['upstream'] += 1
                if 'upstream' in reason:
                    self.upstreamed['upstream'] += 1
            if 'backport:' in subject_l:
                self.total['backport'] += 1
                if 'upstream' in reason:
                    self.upstreamed['backport'] += 1

        self.kernel = None

        # Pull chromeos-5.4 branch
        print('Fetching cros...')
        fetch('kernel-upstream', 'cros')

        print('Fetching upstream...')
        fetch('kernel-upstream', 'upstream')

        # Checkout to target branch
        print('Checkout to', rebase_target, '...')
        checkout('kernel-upstream', rebase_target)

    def get_topic_dispositions(self, topic_list):
        # reload config to import up-to-date disp_overlay
        importlib.reload(rebase_config)
        from rebase_config import disp_overlay

        gids = []
        for topic in topic_list:
            gids.append(self.topics[topic])
        gids = str(gids).replace('[', '(').replace(']', ')')

        self.cur.execute(
            'select disposition,sha,subject,reason from commits where topic in %s' %
            gids)
        dispositions = self.cur.fetchall()
        for i in range(len(dispositions)): # pylint: disable=C0200
            disp = dispositions[i][0]
            sha = dispositions[i][1]
            subject = dispositions[i][2]
            reason = dispositions[i][3]
            # For now, assume there are only pick / drop / replace dispositions
            assert disp in [
                'pick', 'drop', 'replace'], 'Unrecognized disposition.'
            # Modify dispositions according to overlay
            if sha in disp_overlay:
                dispositions[i] = (disp_overlay[sha], sha, subject, reason)

        return dispositions

    # Rebase many topic branches joining them into one topic branch.
    # end_name: name of the target branch
    # topics: list of source topics
    # is_triage: if set, skip over commits that require manual resolution
    def rebase_multiple(self, end_name, topic_list, is_triage=False):
        # reload config to import up-to-date disp_overlay
        importlib.reload(rebase_config)

        print('Checkout to', rebase_target, '...')
        checkout('kernel-upstream', rebase_target)

        if is_triage:
            topic_branch = branch_name('triage', rebase_target, end_name)
            print('Triage mode on. Using branch %s.' % topic_branch)
            with sh.pushd('kernel-upstream'):
                try:
                    sh.git('branch', '-D', topic_branch)
                except sh.ErrorReturnCode_1 as e:
                    pass
        else:
            topic_branch = branch_name(
                self.branch_prefix, rebase_target, end_name)

        try:
            create_head('kernel-upstream', topic_branch)
        except OSError as err:
            print(err)
            print('Branch already exists?')
            return {}

        print('Rebasing topics %s, branch %s' % (topic_list, end_name))

        print('Checkout to %s...' % topic_branch)
        checkout('kernel-upstream', topic_branch)

        dispositions = self.get_topic_dispositions(topic_list)

        dropped = 0
        noconflicts = 0
        autoresolved = 0
        manual = 0
        fixup_manual = 0

        dispositions_with_deps = []
        for i in dispositions:
            sha = i[1]
            if sha in rebase_config.patch_deps:
                for dep in rebase_config.patch_deps[sha]:
                    print('Adding dependency', dep, 'for patch', sha)
                    subject = '(fake subject) Dependency of ' + sha
                    dispositions_with_deps.append(['pick', dep, subject, ''])
            dispositions_with_deps.append(i)

        dispositions = dispositions_with_deps
        for i in dispositions:
            disp = i[0]
            sha = i[1]
            subject = i[2]
            reason = i[3]

            if cp_or_am_in_progress('kernel-upstream'):
                print('cherry-pick or am is currently in progress in kernel-upstream')
                print('resolve and press enter to continue')
                input()

            if disp == 'drop':
                print('Drop commit (%s) %s: %s' % (reason, sha, subject))
                # don't count commits dropped because of upstreaming, to be
                # consistent with genspreadsheet.py
                if reason != 'upstream':
                    dropped += 1
                continue
            print('Pick commit %s: %s' % (sha, subject))
            if disp == 'replace':
                # Replace dispositions are treated as 'pick' to avoid the
                # hassle.
                print('WARNING: commit disposition is replace')

            diff = replacement('kernel-upstream', sha)
            if diff is not None:
                print('Patch replaced by previous conflict resolution:', diff)
                # Make the path absolute
                diff = os.getcwd() + '/' + diff

            override_unresolved = False
            try:
                call_hook(sha, 'pre')
                if diff is None:
                    cherry_pick('kernel-upstream', sha)
                else:
                    apply_patch('kernel-upstream', diff, sha) # sha is only used for debugs
                noconflicts += 1
                # No conflicts, check rerere and continue
                call_hook(sha, 'post')
                continue
            except Exception as error: # pylint: disable=broad-except
                if 'could not build fake ancestor' in str(error):
                    override_unresolved = True
                if debug:
                    sh.mkdir('-p', 'debug/rebase/' + sha)
                    with open('debug/rebase/' + sha + '/cp_am_err', 'w') as f:
                        f.write(str(error))
                call_hook(sha, 'conflict')

            print('Conflicts found.')
            # There were conflicts, check if autoresolved
            # Autostage in git is assumed
            # Files from patches shouldn't be autoresolved, so no path for handling
            # git apply conflicts is added here
            if is_resolved('kernel-upstream') and not override_unresolved:
                print('All resolved automatically.')
                autoresolved += 1
                with sh.pushd('kernel-upstream'):
                    try:
                        sh.git(
                            '-c',
                            'core.editor=true',
                            'am',
                            '--continue')
                        call_hook(sha, 'post')
                    except sh.ErrorReturnCode_128 as e:
                        am_err = 'No changes - did you forget' in str(e.stdout)
                        if am_err:
                            print(
                                'Cherry-pick/am empty due to conflict resolution. Skip.')
                            sh.git(
                                '-c',
                                'core.editor=true',
                                'am',
                                '--abort')
                            call_hook(sha, 'post_empty')
                            continue
                        raise e
            elif is_triage:
                # Conflict requires manual resolution - drop and continue
                print('Commit requires manual resolution. Dropping it for now.')
                manual += 1
                with sh.pushd('kernel-upstream'):
                    sh.git('am', '--abort')
                call_hook(sha, 'post_drop')
                continue

            print(
            """
        Conflict requires manual resolution.
        Resolve it in another window, add the changes by git add, then
        type \'continue\' (c) here.
        Or drop this patch by typing \'drop\' (d). It will be recorded in
        rebase_config.py and dropped in subsequent rebases.
        Or stop the rebase altogether (while keeping the changes that
        were already made) by typing \'stop\' (s).
            """)
            cmd = ''
            while cmd not in ['continue', 'drop', 'stop', 's', 'c', 'd']:
                cmd = input()
            if cmd in ['continue', 'c']:
                # Commit the change and continue
                while not is_resolved('kernel-upstream'):
                    print('Something still unresolved. Resolve and hit enter.')
                    input()
                manual += 1
                with sh.pushd('kernel-upstream'):
                    try:
                        sh.git(
                            '-c', 'core.editor=true', 'am', '--continue')
                        call_hook(sha, 'post')
                    except Exception as e: # pylint: disable=broad-except
                        err_s = str(e)
                        if "did you forget to use 'git add'" in err_s:
                            sh.git('am', '--skip')
                            call_hook(sha, 'post_drop')
                            print('Patch empty due to conflict resolution. Skip.')
                        else:
                            print('git am --continue failed:')
                            print(e)
                            print('Fatal? [y/n]')
                            ans = input()
                            if ans in ['y', 'Y']:
                                return {}
                save_head('kernel-upstream', sha)
            elif cmd in ['drop', 'd']:
                dropped += 1
                # Drop the commit and record as dropped in overlay
                with sh.pushd('kernel-upstream'):
                    sh.git('am', '--abort')
                with open('rebase_config.py', 'a') as f:
                    f.write(
                        "disp_overlay['%s'] = '%s' # %s\n" %
                        (sha, 'drop', subject))
            else:
                print(
                    'Stopped. %s commits dropped, %s applied cleanly, %s resolved'
                    ' automatically, %s needing manual resolution' %
                    (dropped, noconflicts, autoresolved, manual))
                with sh.pushd('kernel-upstream'):
                    sh.git('am', '--abort')
                return {}

        # Apply global reverts
        for sha in rebase_config.global_reverts:
            with sh.pushd('kernel-upstream'):
                sh.git('-c', 'core.editor=true', 'revert', sha)

        for topic in topic_list:
            if topic in rebase_config.topic_fixups:
                # Apply fixups for this particular topic
                for name in rebase_config.topic_fixups[topic]:
                    try:
                        call_hook('[nosha]', 'pre')
                        patch_short = 'patches/fixups/{}.patch'.format(name)
                        patch = os.getcwd() + '/' + patch_short
                        apply_patch('kernel-upstream', patch, '[nosha]')
                        # No conflicts, check rerere and continue
                        print('Applied ' + patch_short + ' fixup for ' + topic + '.')
                        call_hook('[nosha]', 'post')
                        continue
                    except sh.ErrorReturnCode_128:
                        print('Conflict found')
                        with sh.pushd('kernel-upstream'):
                            sh.git('am', '--abort')
                        fixup_manual += 1
                        call_hook('[nosha]', 'post_drop')

        print('Done. %s commits dropped, %s applied cleanly, %s resolved'
              ' automatically, %s+%s needing manual resolution' %
              (dropped, noconflicts, autoresolved, manual, fixup_manual))

        return {'dropped': dropped, 'noconflicts': noconflicts,
                'autoresolved': autoresolved, 'manual': manual, 'fixup_manual': fixup_manual}

    # Shorthand for rebase_multiple
    def rebase_one(self, t, is_triage=False):
        return self.rebase_multiple(t, [t], is_triage)

    # Moves commit into topic dst
    # commit - sha string
    # dst - topic name string
    def topic_move(self, commit, dst):
        dst_gid = self.topics[dst]
        query = "select subject, topic from commits where sha='%s'" % commit
        self.cur.execute(query)
        ret = self.cur.fetchall()
        src_gid = ret[0][1]
        src = ''
        for topic_name in self.topics:
            if self.topics[topic_name] == src_gid:
                src = src_gid
        assert src != '', 'No such topic?'
        query = "update commits set topic=%d where sha='%s'" % (
            dst_gid, commit)
        self.cur.execute(query)
        query = "select subject, topic from commits where sha='%s'" % commit
        self.cur.execute(query)
        ret = self.cur.fetchall()
        assert dst_gid == ret[0][1]
        print('Commit', ret[0][0], 'moved from', src, 'to', dst)

    def topic_list(self, topic):
        dst_gid = self.topics[topic]
        query = "select sha, subject from commits where topic=%d and disposition='pick'" % dst_gid
        self.cur.execute(query)
        ret = self.cur.fetchall()
        for i in ret:
            print(i[0], i[1])


def triage():
    start = datetime.now()
    verify_time = datetime.now() - start # about 0s

    # Check if executor is alive, we'll need it for verifying build
    if do_on_cros_sdk('true', 1) == {}:
        print('Is executor running?')
        return None
    r = Rebaser()
    topic_stats = r.topics
    upstream_stats = r.upstreamed
    total_stats = r.total
    topic_stderr = {}
    for topic in topic_stats:
        topic_branch = branch_name('triage', rebase_target, topic)
        ret = r.rebase_one(topic, is_triage=True)
        topic_stats[topic] = [
            ret['dropped'] +
            ret['noconflicts'] +
            ret['autoresolved'] +
            ret['manual'] +
            ret['fixup_manual'],
            ret['dropped'] +
            ret['noconflicts'] +
            ret['autoresolved'],
            ret['manual'],
            ret['fixup_manual'],
            ret['noconflicts'],
            False]
        print('Verifying build...')

        verify_one_start = datetime.now()
        ret = verify_build(topic_branch)
        verify_one_end = datetime.now()

        verify_time += verify_one_end - verify_one_start

        if ret['exit_code'] == 0:
            print('Built %s succesfully.' % topic)
            topic_stats[topic][4] = True
        else:
            print('Error building %s:' % topic)
            if ret['error_line'] is not None:
                l = ret['error_line']
                reg = re.compile('\x1b\\[[0-9;]*m')
                topic_stderr[topic] = reg.sub(
                    '', '\n'.join(
                        ret['output'].split('\n')[
                            l - 7:l]))
                print(topic_stderr[topic])
            else:
                print('(No error line.)')
            with open(
                 'log/triage/' +
                 topic_branch.replace(
                    '.',
                    '_').replace(
                    '/',
                    '-') +
                 '.txt',
                 'w') as f:
                f.write(ret['output'])

    end = datetime.now()

    elsapsed_total = end - start
    applying_time = elsapsed_total - verify_time

    print(f'Verifying builds took: {verify_time}')
    print(f'Applying patches took: {applying_time}')

    # Pickle the topic stats. Those can be loaded later by
    # Mailing::load_and_notify()
    with open('topic_stats.bin', 'wb') as f:
        pickle.dump(topic_stats, f)
    with open('topic_stderr.bin', 'wb') as f:
        pickle.dump(topic_stderr, f)
    with open('upstream_stats.bin', 'wb') as f:
        pickle.dump(upstream_stats, f)
    with open('total_stats.bin', 'wb') as f:
        pickle.dump(total_stats, f)
    return (topic_stats, topic_stderr)


def fixup():
    print('Current HEAD:')
    sha = head_sha('kernel-upstream')
    print(commit_message('kernel-upstream', sha))
    print('This will record the current HEAD as a fixup.')

    name = input('patch name: ')
    if '/' in name:
        print("patch name can't contains forward slashes!")
        return
    path = 'patches/fixups/{}.patch'.format(name)
    if os.path.isfile(path):
        print('Path exists!')
        yn = input('proceed [y/n]:')
        if yn.lower() not in ['y', 'yes']:
            print('aborting')
            return
    save_head('kernel-upstream', sha, path_override=path)


def merge_topic_branches():
    r = Rebaser()
    topic_dict = r.topics
    topic_list = rebase_config.merge_order_override
    for from_config in rebase_config.merge_order_override:
        if from_config not in topic_dict:
            print(
                "merge_order_override contains topics that aren't in line with topiclist")
            sys.exit()
    for topic in topic_dict:
        if topic not in topic_list:
            topic_list.append(topic)

    topic_branches = [
        branch_name(
            'kernelupstream',
            rebase_target,
            topic) for topic in topic_list]
    merged_branch = branch_name('kernelupstream', rebase_target, None)

    print('checking out to ', rebase_target)
    checkout('kernel-upstream', rebase_target)

    try:
        print('creating head', merged_branch)
        create_head('kernel-upstream', merged_branch)
    except OSError as err:
        print(err)
        print('Branch already exists?')
        return

    print('checking out to ', merged_branch)
    checkout('kernel-upstream', merged_branch)

    for topic_branch in topic_branches:
        print('Merging', topic_branch)
        try:
            with sh.pushd('kernel-upstream'):
                sh.git('merge', '--no-edit', topic_branch)
            continue
        except sh.ErrorReturnCode_1 as error:
            if 'not something we can merge' in str(error):
                print(
                    'topic has no corresponding branch (' +
                    topic_branch +
                    '), skipping')
                continue
        print('Conflict found')
        if is_resolved('kernel-upstream'):
            print('Resolved automatically')
            with sh.pushd('kernel-upstream'):
                sh.git('-c', 'core.editor=/bin/true', 'merge', '--continue')
        else:
            print('Verify automatic resolution or resolve manually')
            print('Enter [s]top to exit or c[ontinue] to proceed')
            cmd = ''
            while cmd not in ['continue', 'stop', 's', 'c']:
                cmd = input()
            if cmd in ['stop', 's']:
                print('Exiting')
                return
    for fu in rebase_config.merge_fixups:
        print('Applying fixup', fu)
        try:
            patch = 'patches/fixups/{}.patch'.format(fu)
            patch = os.getcwd() + '/' + patch
            apply_patch('kernel-upstream', patch, '[merge]')
        except sh.ErrorReturnCode_128:
            print('Conflict found')
            with sh.pushd('kernel-upstream'):
                sh.git('am', '--abort')
            call_hook('[nosha]', 'post_drop')
        except Exception as err: # pylint: disable=broad-except
            print('Uknown error occured:')
            print(err)
            print('Enter [s]top to exit or c[ontinue] to proceed')

# The script only performs basic setup by itself. Specific actions
# are done via an interactive Python shell.
lc = LoggingConsole(local=dict(globals(), **locals()))
lc.interact()
