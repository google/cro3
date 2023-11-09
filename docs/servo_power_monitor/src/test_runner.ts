import {Graph} from './graph';
import {OperatePort} from './operate_port';
import {Ui} from './ui';

export class TestRunner {
  public isOpened = false;
  private CANCEL_CMD = '\x03\n';
  // shell script
  private scripts = `#!/bin/bash -e
function workload () {
  ectool chargecontrol idle
  stress-ng -c 1 -t $1
  echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;
  private ui: Ui;
  private graph: Graph;
  public dut = new OperatePort(0x18d1, 0x504a);
  constructor(ui: Ui, graph: Graph, dut: OperatePort) {
    this.ui = ui;
    this.graph = graph;
    this.dut = dut;
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
  public setupDisconnectEvent() {
    navigator.serial.addEventListener('disconnect', async () => {
      if (this.isOpened) {
        await this.dut.close();
        this.isOpened = false;
      }
    });
  }
}
