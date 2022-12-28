# local-cft

A tool for running CFT services locally using CTRv2, as well as for testing unmerged local changes to CFT services such as cros-dut, cros-test, cros-test-finder, and cros-publish.

# How to run
- Install depot_tools and ensure its in your path
    * go/depot_tools_tutorial
- Run the ```prerequisites.sh``` script to install the prerequisites
    * Installs autossh, docker, and gcloud
- Grab a DUT
    * go/dut-lease
    * If using a lab DUT, get ssh access
        + go/chromeos-lab-duts-ssh
- Head to the chroot/usr/bin folder to run the binary of local-cft
    * Outside of the chroot however, no cros_sdk yet

# Examples runs
Simple test
```
./local-cft -model kevin -board kevin -host chromeos1-row4-rack7-host3 -build R108 -test -tests tast.example.Pass
```

Provision
```
./local-cft -model kevin -board kevin -host chromeos1-row4-rack7-host3 -build R108 -provision
```

Local Updates
```
./local-cft -model kevin -board kevin -host chromeos1-row4-rack7-host3 -build R108 -test -tests tast.example.Pass -localservices cros-test -chroot <chromiumos>/chroot
```
