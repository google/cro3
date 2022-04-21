## Prereqs

 * `sudo pip3 install pandas plotly pyftdi`
 * If running in chroot:
   * wget https://bootstrap.pypa.io/pip/3.6/get-pip.py
   * sudo python ./get-pip.py
   * pip3 install pandas plotly pyftdi
   * Set udev permissions
     * Add the following in `/etc/udev/rules.d/pacman.rules`
     * `
     SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", MODE:="0666"
     SUBSYSTEM=="usb_device", ATTRS{idVendor}=="0403", MODE:="0666"
     `
     * `sudo udevadm control --reload-rules`

# Usage

* pacman.py <options>
  * -s|--single    Take a single voltage, current, power measurement of all rails
  * -t|--time      Length of time to capture in seconds
  * -c|--config    PAC address and configuration file used by servod
  * -O|--output    Directory for output logs
  * -m|--mapping   Rail hierachy mapping used to generate sunburst plot
  * -g|--gpio      PAC address to GPIO Rail mapping

* Example: `sudo ./pacman.py -t 10 -c guybrush_r0_pacs_mainsmt.py`

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
