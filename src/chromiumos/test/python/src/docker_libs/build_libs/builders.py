# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Docker Builder for CFT Services."""

import json
import os
import sys
import time
from typing import List

sys.path.append("../../../")

from src.common.exceptions import (
    GCloudBuildException,  # pylint: disable=import-error,wrong-import-position
)
from src.common.utils import (
    getoutput,  # pylint: disable=import-error,wrong-import-position
)
from src.common.utils import (
    run,  # pylint: disable=import-error,wrong-import-position
)


CWD = os.path.dirname(os.path.abspath(__file__))
CHROOT_DEFAULT = os.path.join(CWD, "../../../../../../../../../../chroot")
REGISTRY_DEFAULT = "us-docker.pkg.dev"
PROJECT_DEFAULT = "cros-registry/test-services"
BUILD_TIMEOUT = 30*60
BUILD_POLL_TIME = 15


class DockerBuilder:
    """Base Class for building Docker images."""

    def __init__(
        self,
        service: str,
        dockerfile: str = "",
        chroot: str = "",
        tags: List[str] = None,
        output: str = "",
        registry_name: str = "",
        cloud_project: str = "",
        labels: List[str] = None,
    ):
        """Validate args + ensure gcloud is ready for use.

        Args:
          service: the service to be built, eg cros-test
          dockerfile: the full path and name of the Dockerfile
          chroot: chroot dir
          tags: tags for naming the image
          output: file which to write the output data from the build
          registry_name: name of the docker registry
          cloud_project: project name of registry
          labels: labels to add to the image.
            Example: ["foo=bar", "foobar=barfoo"]
        """
        self.service = service
        self.dockerfile = dockerfile
        self.build_context = os.path.dirname(self.dockerfile)
        self.chroot = chroot
        self.tags = tags if tags else []
        self.labels = (
            labels if labels else []
        )  # TODO determine if needed in base
        self.output = output  # TODO determine if needed in base
        self.registry_name = registry_name
        self.cloud_project = cloud_project
        self.validate_args()
        self.ensure_gcloud_helpers()

    def validate_args(self):
        """Validate the given args."""
        if not self.service or not self.dockerfile:
            raise Exception("Docker file and Service name required.")

        if os.path.exists("/etc/cros_chroot_version"):
            raise Exception("Must be run outside chroot")

        if not self.chroot:
            self.chroot = CHROOT_DEFAULT
        print(f"Using {self.chroot} for chroot.")

        if not os.path.exists(self.chroot):
            raise Exception(f"Given chroot path does not exist: {self.chroot}")

        if not self.tags:
            self.tags = [f'local-{getoutput("whoami")}']
            print(f"Defaulting tag to {self.tags}")

        if not self.registry_name:
            self.registry_name = REGISTRY_DEFAULT
            print(f"No registry_name given, using default {self.registry_name}")

        if not self.cloud_project:
            self.cloud_project = PROJECT_DEFAULT
            print(f"No cloud_project given, using default {self.cloud_project}")

        print(
            f"Using Docker Registry: {self.registry_name} for"
            f" cloudproject {self.cloud_project}"
        )

        # TODO (dbeckett@), make this a flag
        self.cloud_build_project = "cros-registry"

        self.image_name = self.service
        self.image_path = os.path.join(
            self.registry_name, self.cloud_project, self.image_name
        )

    def ensure_gcloud_helpers(self):
        """Ensure gcloud is setup and ready.

        First call sets up default GCR registries, second call sets up
        Artifact Registry registries.
        """
        getoutput("gcloud --quiet --verbosity=error auth configure-docker")
        getoutput(
            "gcloud --quiet --verbosity=error auth configure-docker"
            " us-docker.pkg.dev"
        )

    def auth_gcloud(self):
        """Auth the gcloud creds, and access token."""
        print("\n== Gcloud helper configuration")
        print(getoutput("docker-credential-gcloud list"))
        print("\n== User Authorization Scopes")
        token = getoutput("gcloud auth print-access-token")
        print("Curling Authorization: Bearer with private token.")
        out = getoutput(
            f'curl -H "Authorization: Bearer {token}"'
            " https://www.googleapis.com/oauth2/v1/tokeninfo",
            log=False
        )
        print(out)

    def write_outfile(self, digest: str):
        """Write the outfile with build info if outfile is given.

        Args:
          digest: digest (aka sha) of the image.
        """
        if not self.output:
            print("No output file given, skipping output file writting.")
            return

        template = {
            "repository": {
                "hostname": self.registry_name,
                "project": self.cloud_project,
            },
            "name": self.image_name,
            "digest": digest,
            "tags": [tag for tag in self.tags],
        }
        with open(self.output, "w") as wf:
            json.dump(template, wf, indent=4)

    def build(self):
        """To be implemented by child class."""
        raise NotImplementedError

    def upload_image(self):
        """To be implemented by child class."""
        raise NotImplementedError


class GcloudDockerBuilder(DockerBuilder):
    """Class for building Docker images via gcloud."""

    def __init__(
        self,
        service: str,
        dockerfile: str = "",
        chroot: str = "",
        tags: List[str] = None,
        output: str = "",
        registry_name: str = "",
        cloud_project: str = "",
        labels: List[str] = None,
    ):
        """Gcloud builder init.

        Args:
          service: the service to be built, eg cros-test
          dockerfile: the full path and name of the Dockerfile
          chroot: chroot dir
          tags: tags for naming the image
          output: file which to write the output data from the build
          registry_name: name of the docker registry
          cloud_project: project name of registry
          labels: labels to add to the image.
            Example: ["foo=bar", "foobar=barfoo"]
        """
        super().__init__(
            service=service,
            dockerfile=dockerfile,
            chroot=chroot,
            tags=tags,
            output=output,
            registry_name=registry_name,
            cloud_project=cloud_project,
            labels=labels,
        )

    def structure_gcloud_tags(self):
        """Translate self.tags to cloudbuild "--substitutions=" args.

        Examples:
          tags=["kevin-postsubmit.123333.211","2385838192918392"]
          translates to: __BUILD_TAG0=us-docker.pkg.dev/cros-registry/test-services/cros-test:kevin-postsubmit.123333.211","2385838192918392  # pylint: disable=line-too-long

        Returns:
          A string of the tags to be substituted into the cloudbuild.yaml
        """
        subs = ""

        for i, tag in enumerate(self.tags):
            subs = subs + f"__BUILD_TAG{i}={self.image_path}:{tag},"

        return subs.rstrip(",")

    def structure_build_labels(self):
        """Translate self.labels to cloudbuild "--substitutions=" args.

        Examples:
          labels=["label1=foo","label2=bar"]
          translates to: __LABEL0=label1=foo","__LABEL1=label2=bar"

        Returns:
          A string ofthe tags to be substituted into the cloudbuild.yaml
        """
        subs = ""
        for i, label in enumerate(self.labels):
            subs = subs + f"__LABEL{i}={label},"

        return subs.rstrip(",")

    def sha_from_cloudbuild_out(self, out: str):
        """Find the "sha:foo" from the cloudbuild log."""
        if not out:
            print("Could not find SHA due to nothing provided.")
            return ""
        outJson = {}
        try:
            outJson = json.loads(out)
        except json.JSONDecodeError:
            print(f"Unable to unmarshal json {out}")
            return ""
        digest = ''
        imageSummary = outJson.get('image_summary')
        if imageSummary:
            digest = imageSummary.get('digest')
        print(f'Using: {digest} as image sha.')
        return digest

    def _find_build_id(self, build_output: str) -> str:
        build_json = {}
        try:
            build_json = json.loads(build_output)
        except json.JSONDecodeError:
            raise Exception("Build ID could not be found from build output.")

        build_id = build_json.get("id")
        if not build_id:
            raise Exception("Build ID was not found in output.")
        return build_id

    def _monitor_build(self, build_id: str) -> str:
        """Monitor the build_id, return when its not "working" or "queued".

        Each loop of the poll will wait BUILD_POLL_TIME seconds to reduce load
        on the RPM quota.
        """
        outp = {}
        start_time = time.time()

        while time.time() - start_time < BUILD_TIMEOUT:
            gcloud_out = getoutput("gcloud builds describe --format=json"
                                   f" --project cros-registry --region us-west4 {build_id}")
            print(f"gcloud describe output:\n{gcloud_out}")
            if not gcloud_out:
                time.sleep(BUILD_POLL_TIME)
                continue

            try:
                outp = json.loads(gcloud_out)
            except json.JSONDecodeError:
                print(f"Found Invalid JSON: {outp}")
                time.sleep(BUILD_POLL_TIME)
                continue

            if outp["status"] in ["WORKING", "QUEUED"]:
                print(f"Build in Queue or Building: {outp['status']}\n")
                time.sleep(BUILD_POLL_TIME)
            else:
                print(f"Build Output: {outp}")
                return outp["status"]

        print(f"Final build status:\n{outp}\n")
        return outp.get("status", "")

    def build(self):
        """Build the Docker image using gcloud build.

        Assumes a cloudbuild.yaml is staged in the same dir as the given
        Dockerfile.
        """
        subs = self.structure_gcloud_tags()
        if self.labels:
            subs = f"{subs},{self.structure_build_labels()}"

        # Use the first tag to search for image.
        search_tag = f"{self.image_path}:{self.tags[0]}"
        self.auth_gcloud()
        cloud_build_cmd = (
            f"gcloud builds submit --config {self.build_context}/cloudbuild.yaml"
            f" {self.build_context} --project {self.cloud_build_project} --region us-west4"
            f' --substitutions={subs} --async --format="json"'
        )

        print(f"Running cloud build cmd: {cloud_build_cmd}")
        print(
            "\n\nNote: This can take a long time (>15 minutes)"
            " for a large container that has no cache. Follow the link provided"
            " a few lines below to see current progress of the build."
            " Build log follows:\n"
        )
        # Stream the cloudbuild cmd.
        out = getoutput(cloud_build_cmd)
        build_id = self._find_build_id(out)

        gcloud_build_final_status = self._monitor_build(build_id)
        if gcloud_build_final_status != 'SUCCESS':
            raise GCloudBuildException(
                f"gcloud build failed with status: {gcloud_build_final_status}"
            )
        out, err,_ = run(
            f"gcloud artifacts docker images describe {search_tag} --format=json",
            shell=True
        )
        print(f"Digest output:\n{out}")
        print(f"Digest stderr:\n{err}")

        self.write_outfile(self.sha_from_cloudbuild_out(out))

    def upload_image(self):
        """Stub for simplicity sakes, as gcloud build automatically uploads."""
        return


class LocalDockerBuilder(DockerBuilder):
    """Class for building Docker images locally using `Docker Build`."""

    def __init__(
        self,
        service: str,
        dockerfile: str = "",
        chroot: str = "",
        tags: List[str] = None,
        output: str = "",
        registry_name: str = "",
        cloud_project: str = "",
        labels: List[str] = None,
    ):
        """Local Docker builder init.

        Args:
          service: the service to be built, eg cros-test
          dockerfile: the full path and name of the Dockerfile
          chroot: chroot dir
          tags: tags for naming the image
          output: file which to write the output data from the build
          registry_name: name of the docker registry
          cloud_project: project name of registry
          labels: labels to add to the image.
            Example: ["foo=bar", "foobar=barfoo"]
        """
        super().__init__(
            service=service,
            dockerfile=dockerfile,
            chroot=chroot,
            tags=tags,
            output=output,
            registry_name=registry_name,
            cloud_project=cloud_project,
            labels=labels,
        )

    def formatted_tags(self):
        """Return formatted self.tags for `docker build`."""
        tagstr = ""
        for tag in self.tags:
            tagstr += f"-t {self.image_path}:{tag} "
        return tagstr.rstrip(" ")

    def formatted_labels(self):
        """Return formatted self.labels for `docker build`."""
        labelstr = ""
        for tag in self.labels:
            labelstr += f"--label {tag} "
        return labelstr.rstrip(" ")

    def sha_from_docker_out(self, tag: str):
        """Get the sha from the built docker image."""
        full_sha = getoutput(
            f'docker inspect --format="{{{{index .RepoDigests 0}}}}" {tag}'
        )
        if "@sha256" not in full_sha:
            raise Exception(f"sha not found from repo digest {full_sha}")

        # If the @sha256 sign is found, split on the @, return just the sha.
        # Example: full_sha = image_path@sha256:<some_long_sha>
        # splits into ['image_path', 'sha256:<some_long_sha>'],
        # return just the "sha256 section"
        return full_sha.split("@")[-1]

    def upload_image(self):
        """Upload the build image to the repo. Must be called after build."""
        self.auth_gcloud()
        run(f"docker push --all-tags {self.image_path}")
        sha = self.sha_from_docker_out(f"{self.image_path}:{self.tags[0]}")
        self.write_outfile(sha)

    def build(self):
        """Build the Docker image using `docker build`.

        Assumes a cloudbuild.yaml is staged in the same dir as the given
        Dockerfile.
        """
        tags = self.formatted_tags()
        labels = self.formatted_labels()

        docker_build_cmd = (
            f"docker build -f {self.dockerfile} {tags} {labels}"
            f" {self.build_context}"
        )

        print(f"Running docker build cmd: {docker_build_cmd}")

        # Stream the docker_build_cmd.
        _, err, status = run(docker_build_cmd, stream=True)
        if status != 0:
            raise GCloudBuildException(
                f"gcloud build failed with err:\n {err}\n"
            )
