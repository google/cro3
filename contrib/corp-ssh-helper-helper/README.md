# corp-ssh-helper-helper

corp-ssh-helper-helper is a helper tool to interact with DUTs from inside the ChromiumOS SDK chroot where corp-ssh-helper is not available.

## Prerequisites

If you have installed a similar tool (e.g. [go/old-corp-ssh-helper-helper](http://go/old-corp-ssh-helper-helper)), please remember to uninstall it before using this.

Namely, there should be nothing existing at `/usr/bin/corp-ssh-helper` in your ChromiumOS SDK chroot.
Also `src/scripts/.local_mounts` shouldn't contain `/usr/bin/corp-ssh-helper`.

```shell
(inside the chroot) $ ls /usr/bin/corp-ssh-helper  # This should fail
(inside the chroot) $ grep /usr/bin/corp-ssh-helper ~/chromiumos/src/scripts/.local_mounts # This shouldn't match with any line
```

## Install

To install corp-ssh-helper-helper, create a symbolic link to corp-ssh-helper-helper-client.py at /usr/bin/corp-ssh-helper inside the ChromiumOS SDK chroot.

To do this, run the following command **inside** the chroot.

```shell
(inside the chroot) $ sudo ln -s ~/chromiumos/src/platform/dev/contrib/corp-ssh-helper-helper/corp-ssh-helper-helper-client.py /usr/bin/corp-ssh-helper
```

## How to use

### Run the server outside the chroot

To use corp-ssh-helper-helper, you need to start the server **outside** the chroot.

```shell
(outside the chroot) ~/chromiumos % src/platform/dev/contrib/corp-ssh-helper-helper/corp-ssh-helper-helper-server.py
```

### Use SSH

After starting the server, you can use SSH in the same way as you do outside the chroot. The client script will automatically forward the connection request to the server running outside the chroot.

```shell
(inside the chroot) $ ssh $DUT
```

The same goes for tools like `tast run` and `cros deploy`.

## Uninstall

You can uninstall this tool by deleting /usr/bin/corp-ssh-helper and ~/chromiumos/corp-ssh-helper-helper.sock **inside** the chroot.

*** note
**Warning**: Do not run the below command outside the chroot as it'll delete the real corp-ssh-helper.
***

```shell
(inside the chroot) $ sudo rm /usr/bin/corp-ssh-helper ~/chromiumos/.corp-ssh-helper-helper.sock
```
