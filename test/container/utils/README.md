# How to build & run a test in the container (All of these steps are outside chroot)

## Setup the artifacts & Build:

1.) cd to

```bash
/dev/test/container/utils
```
2.) Run the following command (with chroot_path and sysroot_path set):

```bash
./build-dockerimage.sh $chroot_path $sysroot_path <tags>
```

## Run the test via testexecservice

3.) cd to `src/platform/dev/test/container/utils`

4.) Run `docker_run.py` with your required args:

**IMPORTANT NOTE 1**: You must create a request.json with a valid test/DUT. See [tauto example](https://source.corp.google.com/chromeos_public/src/platform/dev/src/chromiumos/test/execution/data/tauto.json) and [tast example](https://source.corp.google.com/chromeos_public/src/platform/dev/src/chromiumos/test/execution/data/test.json)

Example of foreground cmd only (pastes the command, you can copy/paste to start it)

```bash
python3 run_docker.py --build=$docker_image_name --input_json=../../../src/chromiumos/test/execution/data/tauto.json --results=$chroot_path/tmp/dockertest --foreground --print_cmd_only
```
Example of full cmd (starts the test for you, and echos stdout)

```bash
python3 run_docker.py --build=$docker_image_name --input_json=../../../src/chromiumos/test/execution/data/tauto.json --results=$chroot_path/tmp/dockertest --foreground
```
Example of full cmd (runs in background), provides results dir.

```bash
python3 run_docker.py --build=$docker_image_name --input_json=../../../src/chromiumos/test/execution/data/tauto.json --results=$chroot_path/tmp/dockertest
```
