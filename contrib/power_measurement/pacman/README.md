## Prereqs

 * If running in chroot you need to install pip:
   * wget https://bootstrap.pypa.io/pip/3.6/get-pip.py
   * sudo python ./get-pip.py
 * Else you can just use pip3 to install python dependicies using the following command.
   * `pip3 install -r requirements.txt`
   * Then set udev permissions as follows so you don't have to run pacman as super user.
     * Add the following in `/etc/udev/rules.d/pacman.rules`
     * `
     SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", MODE:="0666"
     SUBSYSTEM=="usb_device", ATTRS{idVendor}=="0403", MODE:="0666"
     `
     * `sudo udevadm control --reload-rules &&  sudo udevadm trigger`

# Usage

usage: ipython3 [-h] [-s] [-t TIME] [--sample_time SAMPLE_TIME] [-c CONFIG] [-O [OUTPUT]] [-p POLARITY] [-d DEVICE]

Main file for pacman utility

options:
  -h, --help            show this help message and exit
  -s, --single          Use to take a single voltage, current, power measurement of all rails and report GPIO status
  -t TIME, --time TIME  Time to capture in seconds
  --sample_time SAMPLE_TIME
                        Sample time in seconds
  -c CONFIG, --config CONFIG
                        PAC address and configuration file used by servod
  -O [OUTPUT], --output [OUTPUT]
                        Path for log files
  -p POLARITY, --polarity POLARITY
                        Measurements can either be unipolar or bipolar
  -d DEVICE, --device DEVICE
                        Serial number of provisioned pacdebugger to use

* Example: `pacman.py -t 10 -c guybrush_r0_pacs_mainsmt.py`

# Output

* This should dump three files into the output directory.
    By default the output directory is ./Data/<timestamp>

1) accumulatorData.csv which is a csv of the accumulators
2) timeLog.csv which has the time series logs
3) report.html which has four plots inside of it
    * Accumulator table with a summary of results
    * Sunburst diagram of power consumption. You can click on it to browse where power is going
    * Box plots of statistics of time series captures (this is analogous to the servod measurements)
    * Time series plot of the instantaneous measurement. Double click on the rail in the legend to hide all others.
