#!/usr/bin/env python3
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Read the service config and spawn copybot jobs on SourceHut.

Jobs can also be run locally using the --local flag.

Usage:
    service_spawner.py [options...]
"""

# Black compatibility
# pylint: disable=line-too-long
# pylint: disable=invalid-string-quote

import argparse
import base64
import copy
import gzip
import json
import os
import pathlib
import shlex
import subprocess
import sys

import requests  # pylint: disable=import-error
import yaml  # pylint: disable=import-error


def quote_command(cmd):
    """Quote a command so it could be copy-pasted into a shell."""
    return " ".join(shlex.quote(str(x)) for x in cmd)


def get_copybot_command(path_to_copybot, service):
    """Get the command to run copybot."""
    cmd = [path_to_copybot]

    topic = service.get("topic")
    if topic:
        cmd.extend(["--topic", topic])

    prepend_subject = service.get("prepend-subject")
    if prepend_subject:
        cmd.extend(["--prepend-subject", prepend_subject])

    merge_conflict_behavior = service.get("merge-conflict-behavior")
    if merge_conflict_behavior:
        cmd.extend(["--merge-conflict-behavior", merge_conflict_behavior])

    if service.get("add-signed-off-by"):
        cmd.append("--add-signed-off-by")

    for option, arg in [
        ("labels", "--label"),
        ("ccs", "--cc"),
        ("reviewers", "--re"),
        ("hashtags", "--ht"),
        ("exclude-file-patterns", "--exclude-file-pattern"),
    ]:
        vals = service.get(option, [])
        for val in vals:
            cmd.extend([arg, val])

    for urltype in ("upstream", "downstream"):
        url = service[urltype]
        branch = service.get(f"{urltype}-branch")
        if branch:
            url = f"{url}:{branch}"
        cmd.append(url)

    return cmd


def create_manifest(base, copybot_base64, service):
    """Create a SourceHut manifest for a service."""
    manifest = copy.deepcopy(base)
    manifest["triggers"] = service.get("triggers", [])
    manifest["environment"] = {
        "COPYBOT_BASE64": copybot_base64.decode("ascii"),
    }
    cmd = get_copybot_command("./copybot.py", service)

    manifest["tasks"].append({"run-copybot": quote_command(cmd)})
    return manifest


def spawn_manifest(manifest, auth_token, server="builds.sr.ht"):
    """Spawn a job."""
    r = requests.post(
        f"https://{server}/api/jobs",
        json={"manifest": json.dumps(manifest)},
        headers={"Authorization": f"token {auth_token}"},
    )
    r.raise_for_status()


def main():
    """The entry point to the program."""
    here = pathlib.Path(__file__).parent
    parser = argparse.ArgumentParser(description="Copybot Service Spawner")
    parser.add_argument(
        "-c",
        "--config",
        help="Config to use",
        default=here / "service_config.yaml",
        type=pathlib.Path,
    )
    parser.add_argument(
        "-l",
        "--local",
        help="Run jobs locally instead of on SourceHut",
        action="store_true",
    )
    parser.add_argument(
        "--topic",
        help="Only spawn services which match this topic",
    )
    parser.add_argument(
        "-t",
        "--auth-token",
        help="Sourcehut auth token",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        help="Print the manifests instead of spawning them.",
        action="store_true",
    )

    opts = parser.parse_args()
    token = opts.auth_token
    if not token:
        token = os.getenv("SOURCEHUT_TOKEN")

    with open(opts.config) as f:
        config = yaml.safe_load(f)

    base_manifest = config.get("base-manifest", {})
    services = config.get("services", [])

    if opts.topic:
        services = [s for s in services if s.get("topic", "") == opts.topic]

    if not services:
        print("Nothing to do (no matching services defined!)", file=sys.stderr)
        return 0

    copybot_path = (here / "copybot.py").resolve()
    if opts.local:
        rv = 0
        for service in services:
            cmd = get_copybot_command(copybot_path, service)
            print("RUN", quote_command(cmd), file=sys.stderr)
            if not opts.dry_run:
                # pylint: disable=subprocess-run-check
                rv |= subprocess.run(cmd).returncode
                # pylint: enable=subprocess-run-check
        return rv

    # We compress and base64 encode the local copy of copybot to be
    # run on the remote server, allowing local changes to be made
    # without submitting to Gerrit first.
    copybot_gz = gzip.compress(copybot_path.read_bytes())
    copybot_base64 = base64.b64encode(copybot_gz)

    manifests = []
    for service in services:
        manifests.append(create_manifest(base_manifest, copybot_base64, service))

    if opts.dry_run:
        yaml.dump(manifests, sys.stdout)
        return 0

    for manifest in manifests:
        spawn_manifest(manifest, token)

    return 0


if __name__ == "__main__":
    sys.exit(main())
