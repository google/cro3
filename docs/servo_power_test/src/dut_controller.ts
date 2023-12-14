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
    this.isOpened = true;
    await this.dut.write('ectool chargecontrol idle\n');
  }
  public async closeDutPort() {
    if (!this.isOpened) return;
    await this.dut.write('ectool chargecontrol normal\n');
    await this.dut.close();
    this.isOpened = false;
  }
  // initialize the readable stream and check the port
  public async initializePort() {
    await this.dut.select();
    await this.dut.open();
    await this.sendCancelCommand();
    await this.sendCancelCommand();
    await this.sendCancelCommand();
    await this.discardAllDutBuffer(1000);
    const isApShell = await this.checkPortAndLogin();
    await this.dut.close();
    if (!isApShell) {
      throw Error(
        'The port is not for DUT AP shell.\nPlease select the correct port.'
      );
    }
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
      const dutData = (await racePromise) as string;
      // this.runner.readData() is resolved faster
      // that is, some data is read in 1000ms
      return dutData;
    } catch {
      // setTimeOut() is resolved faster
      // that is, no data is read in 1000ms
      await this.dut.cancelRead();
      return '';
    }
  }
  public async discardAllDutBuffer(limitTime: number) {
    let allDutData = '';
    for (;;) {
      const dutData = await this.readDataWithTimeout(limitTime);
      if (dutData === '') {
        // all data is read from DUT
        this.ui.addMessageToConsole(allDutData);
        return allDutData;
      }
      allDutData += dutData;
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
  // Send ctrl+C command to DUT console.
  public async sendCancelCommand() {
    await this.dut.write(this.CANCEL_CMD);
  }
  // If the selected port is AP shell of the DUT, login as root user and return true. Otherwise, return false.
  public async checkPortAndLogin() {
    let isUserNameEntered = false;
    await this.dut.write('\n');
    await this.dut.write('\n');
    for (;;) {
      const dutData = await this.discardAllDutBuffer(100);
      if (dutData.includes('localhost login:')) {
        await this.dut.write('root\n');
        isUserNameEntered = true;
        continue;
      }
      if (dutData.includes('Password:')) {
        if (!isUserNameEntered) {
          await this.dut.write('\n');
          continue;
        }
        await this.dut.write('test0000\n');
        const result = await this.discardAllDutBuffer(1000);
        this.ui.addMessageToConsole(result);
        if (result.includes('Login incorrect')) {
          isUserNameEntered = false;
          continue;
        }
        continue;
      }
      this.dut.write('\nwhoami\n');
      const userName = await this.discardAllDutBuffer(100);
      // userName should be "root".
      if (!userName.includes('root')) return false;
      return true;
    }
  }
}
