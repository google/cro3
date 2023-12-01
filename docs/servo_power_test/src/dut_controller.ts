import {OperatePort} from './operate_port';
import {Ui} from './ui';

export class DutController {
  private CANCEL_CMD = '\x03\n';
  private isOpened = false;
  private ui: Ui;
  public dut = new OperatePort(0x18d1, 0x504a);
  constructor(ui: Ui, dut: OperatePort) {
    this.ui = ui;
    this.dut = dut;
  }
  public async openDutPort() {
    if (this.isOpened) return;
    await this.dut.open();
    console.log('dutPort is opened\n'); // for debug
    this.isOpened = true;
    await this.dut.write('ectool chargecontrol idle\n');
  }
  public async closeDutPort() {
    if (!this.isOpened) return;
    await this.dut.write('ectool chargecontrol normal\n');
    await this.dut.close();
    console.log('dutPort is closed\n'); // for debug
    this.isOpened = false;
  }
  public async readData() {
    const chunk = await this.dut.read();
    return chunk;
  }
  // Return true if no data appears on DUT serial console while waiting for 1000ms. Otherwise, return false.
  private async readDataWithTimeout(limitTime: number) {
    const racePromise = Promise.race([
      this.readData(),
      new Promise((_, reject) => setTimeout(reject, limitTime)),
    ]);
    try {
      await racePromise;
      // this.runner.readData() is resolved faster
      // that is, some data is read in 1000ms
      return false;
    } catch {
      // setTimeOut() is resolved faster
      // that is, no data is read in 1000ms
      await this.dut.readCancel();
      console.log('read all data');
      return true;
    }
  }
  public async discardAllDutBuffer() {
    for (;;) {
      const allDataIsRead = await this.readDataWithTimeout(1000);
      if (allDataIsRead) {
        // all data is read from DUT
        break;
      }
    }
  }
  public async runWorkload(customScript: string) {
    const script = `\nfunction workload () {
  ${customScript}
}
sleep 3
echo "start"
workload 1> ./test_out.log 2> ./test_err.log
echo "end"
sleep 3
echo "stop"\n`;
    await this.dut.write(`\necho "${btoa(script)}" | base64 -d | bash\n`);
  }
  public async sendCancel() {
    await this.dut.write(this.CANCEL_CMD);
  }
}
