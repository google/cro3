# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Disable pylint noise
# pylint: disable=import-error
# pylint: disable=redefined-outer-name
# pylint: disable=input-builtin
# pylint: disable=broad-except

"""Creates a bisection branch between two KCR results"""

import sh
from githelpers import (
    checkout,
    cherry_pick,
    commit_message,
    commit_subject,
    create_head,
    diff,
    is_merge,
    list_shas,
    patch_title,
    revert
)

FIXUP_PREFIX = 'FIXUP: '

def kernelupstream_branch(ver):
    """Map kernel version to branch name."""
    branch_prefix = 'cros/merge/continuous/chromeos-kernelupstream-'
    return f'{branch_prefix}{ver}'

def get_patches(ver):
    """List of patches above upstream tag.

    Each patch is described as a dictionary with sha, content-hash,
    commit-title and change-id fields.
    """

    branch = kernelupstream_branch(ver)

    checkout('kernel-upstream', branch)
    shas = list_shas('kernel-upstream', f'v{ver}..HEAD')
    shas_cnt = len(shas)

    print(f'Processing {shas_cnt} patches from {branch}...')

    res = []
    for sha in shas:
        content_hash = patch_title('kernel-upstream', sha)
        commit_title = commit_subject('kernel-upstream', sha)

        commit_msg = commit_message('kernel-upstream', sha).splitlines()
        change_id_prefix = 'Change-Id: '
        change_id = None
        for msg_line in commit_msg:
            line = msg_line.strip()
            if line.startswith(change_id_prefix):
                change_id = line[len(change_id_prefix):]
                break

        entry = {}
        entry['sha'] = sha
        entry['content-hash'] = content_hash
        entry['commit-title'] = commit_title
        entry['change-id'] = change_id
        res.append(entry)

    print('Done.')

    res.reverse()
    return res

def is_same(patch1, patch2):
    """Decides whether two patches are the same change.

    The patches might be different in content due to the rebase,
    hence this function uses Change-Ids for comparison if available,
    or patch titles if not.
    """

    chid1 = patch1['change-id']
    chid2 = patch2['change-id']
    title1 = patch1['commit-title']
    title2 = patch2['commit-title']

    # prioritize change-id for commit comparison if available
    if chid1 is not None and chid2 is not None:
        return chid1 == chid2
    return title1 == title2

def dispositions(patches_begin, patches_end):
    """List a sequence of Chromium OS patch operations that transform {begin} into {end}."""

    # Collect all content-hashes that are duplicated across the two lists.
    dupe_content_hashes = set()
    for patch1 in patches_begin:
        for patch2 in patches_end:
            if patch1['content-hash'] == patch2['content-hash']:
                dupe_content_hashes.add(patch1['content-hash'])

    # Remove the duplicates from both lists.
    # This also removes all empty commits as the content-hash ignores
    # commit messages, and there are many of them on both branches.
    diff_patches_begin = []
    for patch in patches_begin:
        if patch['content-hash'] not in dupe_content_hashes:
            diff_patches_begin.append(patch)

    diff_patches_end = []
    for patch in patches_end:
        if patch['content-hash'] not in dupe_content_hashes:
            diff_patches_end.append(patch)

    # Prepare a sequence of dispositions to trasnform the private
    # Chromium OS patches state from {begin} into that from {end}
    dispositions_naive = []
    for patch in diff_patches_begin:
        dispositions_naive.append({'disposition': 'revert', 'patch': patch})
    for patch in diff_patches_end:
        dispositions_naive.append({'disposition': 'pick', 'patch': patch})

    # Look for replacements, i.e. patches different on {begin} and {end}
    # They will be squashed together
    to_squash = []
    for disp1 in dispositions_naive:
        for disp2 in dispositions_naive:
            d1 = disp1['disposition']
            d2 = disp2['disposition']
            patch1 = disp1['patch']
            patch2 = disp2['patch']

            is_fixup = patch1['commit-title'].startswith(FIXUP_PREFIX)
            # squash pairs of revert-apply other than fixups
            if d1 == 'revert' and d2 == 'pick' and is_same(patch1, patch2) and not is_fixup:
                to_squash.append({'revert': patch1, 'pick': patch2})

    # Rewords the dispositions so that instead of simple pick/revert a wider
    # Array of operations is supported:
    # - Pick:
    #   * fixup_old: a fixup previously applied to the patch, reverted before pick
    #   * fixup_new: a fixup supposed to be applied to the patch, applied after pick
    #   * sha: sha of commit to pick
    #   * title: subject of the patch
    # - Revert:
    #   * sha: sha of commit to revert
    #   * title: subject of the patch
    # - Replace:
    #   * fixup_old: a fixup previously applied to the patch, reverted before revert of old
    #   * fixup_new: a fixup supposed to be applied to the patch, applied after pick of new
    #   * old: sha of patch as of {begin}
    #   * new: sha of patch as of {end}
    #   * title: subject of old
    #
    # The fixup fields will be populated later
    dispositions = []
    for disp in dispositions_naive:
        d = disp['disposition']
        patch = disp['patch']
        if d == 'revert':
            squashed = False
            for squash in to_squash:
                if is_same(patch, squash['revert']):
                    dispositions.append({
                        'disposition': 'replace',
                        'old': patch['sha'],
                        'new': squash['pick']['sha'],
                        'fixup_old': None,
                        'fixup_new': None,
                        'title': patch['commit-title']
                    })
                    squashed = True
                    break
            if not squashed:
                dispositions.append({
                    'disposition': 'revert',
                    'sha': patch['sha'],
                    'title': patch['commit-title']
                })
        elif d == 'pick':
            skip = False
            for squash in to_squash:
                if is_same(patch, squash['pick']):
                    skip = True
                    break
            if not skip:
                dispositions.append({
                    'disposition': 'pick',
                    'sha': patch['sha'],
                    'fixup_old': None,
                    'fixup_new': None,
                    'title': patch['commit-title']
                })

    # Populates the fixup_* fields and marks the moved fixups for
    # removal from individual dispositions.
    fixups_to_skip = []
    for d1 in dispositions:
        disp = d1['disposition']
        field = None
        if disp == 'revert':
            field = 'fixup_old'
        elif disp == 'pick':
            field = 'fixup_new'

        if d1['title'].startswith(FIXUP_PREFIX):
            title = d1['title'].strip(FIXUP_PREFIX)
            for d2 in dispositions:
                if d2['title'] == title:
                    d2[field] = d1['sha']
                    fixups_to_skip.append(d1['sha'])

    # Removes the fixups identified above.
    dispositions = [d for d in dispositions if ('sha' not in d) or (d['sha'] not in fixups_to_skip)]

    return dispositions

def upstream_picks(begin, end):
    """Lists all upstream commits between {begin} and {end}"""

    tag1 = f'v{begin}'
    tag2 = f'v{end}'

    checkout('kernel-upstream', tag2)
    shas = list_shas('kernel-upstream', f'{tag1}..HEAD')

    shas.reverse()

    # skip merges, as they can't be cherry-picked directly
    # and are always empty on upstream.
    return [sha for sha in shas if not is_merge('kernel-upstream', sha)]

def handle_error(e):
    """UI for interaction with conflicts and other errors"""

    while True:
        print('Conflict occurred')
        print('Options:')
        print('c/continue -- proceed, type after resolving the conflict and comitting')
        print('s/stop -- halt the entire process')
        print('d/drop -- drop the patch')
        print('?/what -- print the exception')

        cmd = ''
        while cmd not in ['c', 'continue', 's', 'stop', 'd', 'drop', '?', 'what']:
            cmd = input()
        if cmd in ['c', 'continue']:
            return 'c'
        if cmd in ['s', 'stop']:
            return 's'
        if cmd in ['d', 'drop']:
            return 'd'
        if cmd in ['?', 'what']:
            print(e)

def squash(top_patches):
    """Squashes len(top_patches) commits

    The commit message is the top_patches list formatted in a human-readable way.
    This list would best reflect the subjects of the squashed commits, but it can
    be anything as long as it's a list of strings.
    """

    n = len(top_patches)
    msg = 'Squash: ['
    for patch in top_patches:
        msg += patch
        msg += ', '
    msg += ']'

    with sh.pushd('kernel-upstream'):
        sh.git('reset', f'HEAD~{n}')

        err = None
        try:
            sh.git('add', '-A')
            sh.git('commit', '-m', msg)
        except sh.ErrorReturnCode_1 as e:
            if 'nothing to commit' in str(e):
                print('Replace result is null, proceed without commit')
                return False
            err = e
        except Exception as e:
            err = e

        if err is not None:
            choice = handle_error(err)
            return choice == 's'

    return False

# Setup begin and end versions
begin = '5.18-rc6'
end = '5.18'

# Resultant branch name format
bisect_branch = f'kernelupstream-bisect-{begin}-{end}'

begin_patches = get_patches(begin)
end_patches = get_patches(end)

# Print informative statistics
disps = dispositions(begin_patches, end_patches)
reverts = 0
picks = 0
replacements = 0
for disp in disps:
    d = disp['disposition']
    if d == 'revert':
        reverts += 1
    elif d == 'pick':
        picks += 1
    elif d == 'replace':
        replacements += 1

print('Computed dispositions of Chromium OS patches:')
print(f'Patches to revert: {reverts}')
print(f'Patches to pick: {picks}')
print(f'Patches to replace: {replacements}')

from_upstream = upstream_picks(begin, end)
from_upstream_count = len(from_upstream)
print(f'Patches that entered upstream between {begin} and {end}: {from_upstream_count}')

print('Begin work on constructing a bisection branch...')

print(f'Checkout {begin}')
checkout('kernel-upstream', kernelupstream_branch(begin))

print(f'Create branch {bisect_branch}')
create_head('kernel-upstream', bisect_branch)
checkout('kernel-upstream', bisect_branch)

print('Cherry-pick upstream patches')
for sha in from_upstream:
    print('Pick', commit_subject('kernel-upstream', sha))

    err = None
    try:
        cherry_pick('kernel-upstream', sha, use_am=False)
        continue
    except Exception as e:
        if 'The previous cherry-pick is now empty' in str(e):
            print('cherry-pick empty')
            continue
        err = e

    choice = handle_error(err)
    if choice == 'c':
        continue
    if choice == 's':
        break
    if choice == 'd':
        with sh.pushd('kernel-upstream'):
            sh.git('cherry-pick', '--abort')
        continue

print('Revert unneeded Chromium OS patches')
for disp in disps:
    if disp['disposition'] != 'revert':
        continue
    sha = disp['sha']

    print('Revert', commit_subject('kernel-upstream', sha))

    err = None
    try:
        revert('kernel-upstream', sha)
        continue
    except Exception as e:
        err = e

    choice = handle_error(err)
    if choice == 'c':
        continue
    if choice == 's':
        break
    if choice == 'd':
        with sh.pushd('kernel-upstream'):
            sh.git('revert', '--abort')
        continue

print('Update changed Chromium OS patches')
for disp in disps:
    d = disp['disposition']
    if d == 'replace':
        to_revert = disp['old']
        to_pick = disp['new']
        print('Replace', commit_subject('kernel-upstream', to_revert))
        print(f'{to_revert} -> {to_pick}')
    elif d == 'pick':
        to_revert = None
        to_pick = disp['sha']
        print('Pick', commit_subject('kernel-upstream', to_pick))
    else:
        continue

    fixup_old = disp['fixup_old']
    fixup_new = disp['fixup_new']

    count = 1
    if d == 'replace':
        count = 2
    if fixup_old is not None:
        print(f'Squashing revert of old fixup: {fixup_old}')
        count += 1
    if fixup_new is not None:
        print(f'Squashing cherry-pick of new fixup: {fixup_new}')
        count += 1

    applied = []
    if fixup_old is not None:
        try:
            revert('kernel-upstream', fixup_old)
        except Exception as e:
            choice = handle_error(e)
            if choice == 's':
                break
            if choice == 'd':
                with sh.pushd('kernel-upstream'):
                    sh.git('revert', '--abort')
                continue
        applied.append(commit_subject('kernel-upstream', fixup_old))

    if to_revert is not None:
        try:
            revert('kernel-upstream', to_revert)
        except Exception as e:
            choice = handle_error(e)
            if choice == 's':
                break
            if choice == 'd':
                with sh.pushd('kernel-upstream'):
                    sh.git('revert', '--abort')
                continue
        applied.append(commit_subject('kernel-upstream', to_revert))

    merge = is_merge('kernel-upstream', to_pick)
    try:
        if merge:
            cherry_pick('kernel-upstream', to_pick, use_am=True)
        else:
            cherry_pick('kernel-upstream', to_pick, use_am=False)
        applied.append(commit_subject('kernel-upstream', to_pick))
    except Exception as e:
        if '--allow-empty' in str(e):
            print('Nothing to commit, skipping')
        else:
            choice = handle_error(e)
            if choice == 'c':
                applied.append(commit_subject('kernel-upstream', to_pick))
            elif choice == 's':
                break
            elif choice == 'd':
                with sh.pushd('kernel-upstream'):
                    rollback = len(applied)
                    if merge:
                        sh.git('am', '--abort')
                    else:
                        sh.git('cherry-pick', '--abort')
                    sh.git('reset', '--hard', f'HEAD~{rollback}')
                continue

    if fixup_new is not None:
        try:
            cherry_pick('kernel-upstream', fixup_new, use_am=False)
        except Exception as e:
            choice = handle_error(e)
            if choice == 's':
                break
            if choice == 'd':
                with sh.pushd('kernel-upstream'):
                    rollback = len(applied)
                    sh.git('cherry-pick', '--abort')
                    sh.git('reset', '--hard', f'HEAD~{rollback}')
                continue
        applied.append(commit_subject('kernel-upstream', fixup_new))

    if len(applied) > 1:
        squash_stop = squash(applied)
        if squash_stop:
            break

# Apply a special patch to account for any remaining difference between this bisection
# branch and the {end}.
print(f'Creating a final commit to make the tree exactly the same as {end}')
end_branch = kernelupstream_branch(end)
rem_diff = diff('kernel-upstream', f'HEAD..{end_branch}')
rem_diff_path = '/tmp/kcr_bisect_rem.patch'
with open(rem_diff_path, 'w') as f:
    f.write(rem_diff)
with sh.pushd('kernel-upstream'):
    sh.git('apply', rem_diff_path)
    sh.git('add', '-A')
    sh.git('commit', '-m', f'KCR BISECT: Commit all remaining diff from {end}')
