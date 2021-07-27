# Syz-Repro Automation

## Setup

To build syz-repro-automation, first set up your GOPATH environment variable and then run the following commands

	$ GOPATH_DIR=`echo $GOPATH | cut -d ':' -f1`
	$ mkdir -p ${GOPATH_DIR}/src/github.com/google
	$ export GO111MODULE=off
	$ ln -s $(pwd) ~/repos/GOPATH/src/github.com/google/syz-repro-automation
	$ go build

## Usage

To run syz-repro on a single log file, the user can run

	$ ./syz-repro-automation -logfile [-flags] PATH/TO/LOGFILE

The available flags are:
- `-model`: specify what model device to lease (default: garg)
- `-minutes`: specify how many minutes to lease the device for (default: 60)
- `-imageid`: specify the kernel image id to flash onto the DUT (default: lookup the latest image for the DUT board)
