# How to build & run a test in the container (All of these steps are outside chroot)

## Setup the artifacts for build:

1.) cd to

```bash
/dev/test/container/utils
```
2.) Run the following command:

```bash
export chroot_path=path/to/your/chroot/base && export sysroot_path=build/<a board that you have built> && export output_path=<where in the sysroot you want the artifacts to go> && sh container_prep_caller.sh`
```

Example:
```bash
export chroot_path=/usr/local/google/home/ldap/drive2/chromiumos/chroot && export sysroot_path=build/hana && export output_path=tmp/dockerout && sh container_prep_caller.sh
```

## Build the container

3.) cd to the output. Example:

```bash
cd ../chroot/build/hana/tmp/dockerout/
```

4.) Run:

```bash
docker build -t testcontainer -f Dockerfile .
```

## Run the test via testexecservice

5.) cd to `src/platform/dev/test/container/utils`

6.) Run `docker_run.py` with your required args:

**IMPORTANT NOTE 1**: You must create a request.json with a valid test/DUT. See [tauto example](https://source.corp.google.com/chromeos_public/src/platform/dev/src/chromiumos/test/execution/data/tauto.json) and [tast example](https://source.corp.google.com/chromeos_public/src/platform/dev/src/chromiumos/test/execution/data/test.json)

Example of foreground cmd only (pastes the command, you can copy/paste to start it)

```bash
python3.6 run_docker.py --build=autotest_jul19 --input_json=../../../src/chromiumos/test/execution/data/tauto.json --results=/usr/local/google/home/dbeckett/drive2/cros_2021/chroot/tmp/dockertest --foreground --cmd_only
```

Example of self running (It launches docker, runs, exits, all in background, provides results dir):

```bash
python3.6 run_docker.py --build=autotest_jul19 --input_json=../../../src/chromiumos/test/execution/data/tauto.json --results=/usr/local/google/home/dbeckett/drive2/cros_2021/chroot/tmp/dockertest --cmd_only
```
