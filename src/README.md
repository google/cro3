# platform/dev golang development

[TOC]

## Outside chroot w/ VSCode

For lightweight development outside of the chroot,
run the following:

Setup the chroot go build env/deps, which is what will
be present when building/running through cros_sdk:

```sh
cros_sdk
cros_workon --host start test-server
sudo emerge test-server

```

Add the following to your ~/.bashrc:

```sh
# Enable building go modules from your $GOPATH
# Details: ttps://blog.golang.org/go116-module-changes
go env -w  GO111MODULE=auto

# Setup local go dir where binaries are installed
mkdir -p ~/go
export GOPATH=$HOME/go

# Set your GOPATH to find this code
export GOPATH=${GOPATH}:$HOME/chromiumos/src/platform/dev

# Set your GOPATH to all of the deps that will be present
# when building/running from the chroot/portage
CHROMEOS_SRC=~/chromiumos
export GOPATH=${GOPATH}:${CHROMEOS_SRC}/chroot/usr/lib/gopath

# Add Tast repos to GOPATH
export GOPATH=${GOPATH}:$HOME/chromiumos/src/platform/tast-tests
export GOPATH=${GOPATH}:$HOME/chromiumos/src/platform/tast

```

Then launch VS Code:

```sh
cd ~/chromiumos/src/platform
code dev
```
