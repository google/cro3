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

To run syz-repro on a directory, the user can run

	$ ./syz-repro-automation -logdir PATH/TO/LOGDIR

Your root directory at `PATH/TO/LOGDIR` must be structured in the following format:
```
logdir
│   logopts.yaml
└───bugs
	└───189546178
	│  	└───log0
	└───188960160
		└───log0
```
Note each subdirectory in `bugs` is a numeric buganizer ID.

Then `logopts.yaml` should be structured as follows:
```yaml
bugs:
- id: 189546178
  dut:
    imageid: R93-13996.0.0-48962-8846054154814192240
    model: pompom
- id: 188960160
  dut:
    imageid: R93-13984.0.0-48668-8846614155709648032
    model: limozeen
```
