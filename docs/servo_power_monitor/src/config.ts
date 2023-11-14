import {Graph} from './graph';
import {PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {TestRunner} from './test_runner';
import {Ui} from './ui';

export class Config {
  private INTERVAL_MS = 100;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private powerDataList: Array<PowerData> = [];
  private graph: Graph;
  private script = '';
  public halt = true;
  private inProgress = false;
  constructor(
    ui: Ui,
    graph: Graph,
    servoController: ServoController,
    runner: TestRunner,
    customScript: string
  ) {
    this.ui = ui;
    this.graph = graph;
    this.servoController = servoController;
    this.runner = runner;
    this.script = `#!/bin/bash -e
function workload () {
${customScript}
}
ectool chargecontrol idle
sleep 3
echo "start"
workload 1> ./test_out.log 2> ./test_err.log
echo "end"
sleep 3
ectool chargecontrol normal\n`;
  }
  private changeHaltFlag(flag: boolean) {
    this.halt = flag;
    this.servoController.halt = flag;
    this.ui.enabledRecordingButton(this.halt);
  }
  private kickWriteLoop() {
    const f = async () => {
      while (!this.halt) {
        if (this.inProgress) {
          console.error('previous request is in progress! skip...');
        } else {
          this.inProgress = true;
        }
        await this.servoController.writeInaCommand();
        await new Promise(r => setTimeout(r, this.INTERVAL_MS));
      }
    };
    setTimeout(f, this.INTERVAL_MS);
  }
  private async readLoop() {
    while (!this.halt) {
      const currentPowerData = await this.servoController.readData();
      this.inProgress = false;
      if (currentPowerData === undefined) continue;
      this.ui.setSerialOutput(currentPowerData.originalData);
      const e: PowerData = [new Date().getTime(), currentPowerData.power];
      this.powerDataList.push(e);
      this.graph.updateGraph(this.powerDataList);
    }
  }
  public async start() {
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
  }
  public async stop() {
    this.changeHaltFlag(true);
    this.inProgress = false;
  }
}
