import {serialPort} from './serialport';
import {addMessageToConsole, closePopup, readInputValue} from './ui';

export class dutSerialConsole {
  dut = new serialPort();
  isOpened = false;
  CANCEL_CMD = '\x03\n';
  // shell script
  scripts = `#!/bin/bash -e
function workload () {
  ectool chargecontrol idle
  stress-ng -c 1 -t \\$1
  echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;

  async selectPort() {
    await this.dut.open(0x18d1, 0x504a);
    this.isOpened = true;
    addMessageToConsole('DutPort is selected');
    for (;;) {
      const chunk = await this.dut.read();
      addMessageToConsole(chunk);
    }
  }
  async formSubmit(e: Event) {
    e.preventDefault();
    if (!this.isOpened) {
      closePopup();
      return;
    }
    await this.dut.write(readInputValue() + '\n');
  }
  // send cancel command to serial port when ctrl+C is pressed in input area
  async cancelSubmit(e: KeyboardEvent) {
    if (!this.isOpened) {
      closePopup();
      return;
    }
    if (e.ctrlKey && e.key === 'c') {
      await this.dut.write(this.CANCEL_CMD);
    }
  }
  async executeScript() {
    if (!this.isOpened) {
      closePopup();
    } else {
      await this.dut.write('cat > ./example.sh << EOF\n');
      await this.dut.write(this.scripts);
      await this.dut.write('EOF\n');
      await this.dut.write('bash ./example.sh\n');
    }
  }
  async disconnectPort() {
    if (this.isOpened) {
      await this.dut.close();
      this.isOpened = false;
    }
  }
}
