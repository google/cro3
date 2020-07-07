# -*-coding: utf-8 -*-

"""Module that generates CL for cherry-picked commit."""

import subprocess
import os

from cvelib import common


class CLGeneratorException(Exception):
    """Exception class for clgenerator."""


def create_cls(bug_id, kernels):
    """Generates CLs for given kernels."""
    cl_map = {}

    for kern in kernels:
        branch = common.get_cherry_pick_branch(bug_id, kern)
        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kern)

        common.do_checkout(kern, branch, kernel_path)

        # Generates CL.
        push_cmd = get_git_push_cmd(kern)
        output = do_push(push_cmd, kern, kernel_path)

        cl_map[kern] = parse_cls_output(output)

    return cl_map


def get_git_push_cmd(kernel):
    """Generates push command to chromeos branch."""
    branch = common.get_cros_branch(kernel)

    return f'git push cros HEAD:refs/for/{branch}'


def do_push(push_cmd, kernel, kernel_path):
    """Pushes to branch."""
    try:
        output = subprocess.check_output(push_cmd, stderr=subprocess.DEVNULL, cwd=kernel_path)
    except:
        raise CLGeneratorException('Push failed for %s' % kernel)

    return output


def parse_cls_output(push_msg):
    """Returns CL links from push output."""
    cl_link = []

    msg = push_msg.splitlines()

    for line in msg:
        if 'remote:   https://chromium-review' in line:
            link = line.split()[1]
            cl_link.append(link)

    return cl_link