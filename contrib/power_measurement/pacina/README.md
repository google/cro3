## Prerequisite

Script assumes that FTDI USB-to-I2C device(s) are used to communicate to and
from the current sensor ICs. As such, appropriate udev permissions need to be
set.

### Setting udev rules

Add the following in `/etc/udev/rules.d/11-ftdi.rules`

```
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", GROUP="plugdev", MODE="0660"`
SUBSYSTEM=="usb_device", ATTR{idVendor}=="0403", GROUP="plugdev", MODE="0660"
```

### Python Setup

Script can be run both inside and outside of chroot and requires the following packages:

```
pandas
plotly
pyftdi
```

If running in chroot, run the following commands to install the required
packages:

```
wget https://bootstrap.pypa.io/pip/3.6/get-pip.py
sudo python ./get-pip.py
sudo pip3 install pandas plotly pyftdi
```

It is recommended to run the script outside of chroot, as the setup described in
this documennt requires to run `pacina.py` in `sudo`.

### Logging power

`usage: pacina.py [-h] [-s] [-t TIME] [--configs [CONFIGS ...]]
    [--power_state {undefined,z5,z2,z1,s5,s4,s3,s0ix,plt-1h,plt-10h}] [-O
    OUTPUT] [-p {unipolar,bipolar}] [--ftdi-urls [FTDI_URLS ...]] [--dut-info
    DUT_INFO] [--dut DUT] [--sample-time SAMPLE_TIME] [-d] [-v]`

```
options:
-h, --help
       Show this help message and exit

-s, --single
       Use to take a single voltage, current power measurement of all rails

-t TIME, --time TIME
       Time to capture in seconds

--configs [CONFIGS ...]
       Current sensor configuration files. Supports both servod and pacman formats. Number of config files needs to
       match number of number of FTDI URLs.

--power_state {undefined,z5,z2,z1,s5,s4,s3,s0ix,plt-1h,plt-10h}
       Power State Information

-O OUTPUT, --output OUTPUT
       Path for log files

-p {unipolar,bipolar}, --polarity {unipolar,bipolar}
       Measurements can either be unipolar or bipolar

--ftdi-urls [FTDI_URLS ...]
       FTDI URLs. Number of URLs needs to match number of config files

--dut-info
       DUT_INFO JSON file containing DUT related information

--dut DUT
       Target DUT. Only used when --dut_info is used.

--sample-time SAMPLE_TIME
       Target sample time in seconds

-d, --debug
       Print debug messages

-v, --verbose
       Print verbose messages
```

### Outputs
Following outputs are generated when taking a single measurement (`-s, --single`):
* singleLog.csv containing instantaneous voltage, current and power readings for the rails specified in the config(s).

Following outputs are generated when taking continuous measurements:
* timeLog.csv - raw power reads for the rails specified in the config(s).
* summary.csv - summary of the average power for the rails specified in the config(s).
* summary.html - containing rail time series plots and summary tables.

If `dut_info` is provided, following additional file is generated:
* testinfo.json - containing DUT and test related information.
