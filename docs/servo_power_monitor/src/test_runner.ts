import {OperatePort} from './operate_port';
import {Ui} from './ui';

export class TestRunner {
  private CANCEL_CMD = '\x03\n';
  private isOpened = false;
  private scripts = '';
  private ui: Ui;
  public dut = new OperatePort(0x18d1, 0x504a);
  constructor(ui: Ui, dut: OperatePort) {
    this.ui = ui;
    this.dut = dut;
  }
  public setScript() {
    const customScript = this.ui.readInputScript();
    this.scripts = `#!/bin/bash -e
function workload () {
  ${customScript}
}
sleep 3
echo "start"
workload 1> ./test_out.log 2> ./test_err.log
echo "end"
sleep 3
echo "stop"
ectool chargecontrol normal 1> ./test_out.log 2> ./test_err.log\n`;
  }
  public async openDutPort() {
    if (this.isOpened) return;
    await this.dut.open();
    console.log('dutPort is opened\n');
    this.isOpened = true;
    await this.dut.write('ectool chargecontrol idle\n');
  }
  public async closeDutPort() {
    if (!this.isOpened) return;
    await this.dut.write('ectool chargecontrol normal\n');
    await this.dut.close();
    console.log('dutPort is closed\n');
    this.isOpened = false;
  }
  public async readData() {
    const chunk = await this.dut.read();
    return chunk;
  }
  public async copyScriptToDut() {
    await this.dut.write('cat > ./example.sh << EOF\n');
    await this.dut.write(btoa(this.scripts) + '\n');
    await this.dut.write('EOF\n');
  }
  public async executeScript() {
    await this.dut.write('base64 -d ./example.sh | bash\n');
  }
  public async executeCommand(s: string) {
    await this.dut.write(s);
  }
  public async sendCancel() {
    await this.dut.write(this.CANCEL_CMD);
  }
}
