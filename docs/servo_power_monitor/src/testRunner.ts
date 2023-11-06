import {OperatePort} from './operatePort';

export class testRunner {
  public isOpened = false;
  private CANCEL_CMD = '\x03\n';
  // shell script
  private scripts = `#!/bin/bash -e
function workload () {
  ectool chargecontrol idle
  stress-ng -c 1 -t \\$1
  echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;
  private dut: OperatePort;
  constructor(dut: OperatePort) {
    this.dut = dut;
  }
  private async readDutLoop(addMessageToConsole: (s: string) => void) {
    addMessageToConsole('DutPort is selected');
    for (;;) {
      const chunk = await this.dut.read();
      addMessageToConsole(chunk);
    }
  }
  public async selectPort(addMessageToConsole: (s: string) => void) {
    await this.dut.open(true);
    this.isOpened = true;
    this.readDutLoop(addMessageToConsole);
  }
  public async executeScript() {
    await this.dut.write('cat > ./example.sh << EOF\n');
    await this.dut.write(this.scripts);
    await this.dut.write('EOF\n');
    await this.dut.write('bash ./example.sh\n');
  }
  public async executeCommand(s: string) {
    await this.dut.write(s);
  }
  public async sendCancel() {
    await this.dut.write(this.CANCEL_CMD);
  }
  public setupDisconnectEvent() {
    navigator.serial.addEventListener('disconnect', async () => {
      if (this.isOpened) {
        await this.dut.close();
        this.isOpened = false;
      }
    });
  }
}
