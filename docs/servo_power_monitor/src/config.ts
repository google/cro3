import {Graph} from './graph';
import {AnnotationData, PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {TestRunner} from './test_runner';
import {Ui} from './ui';

export class Config {
  private INTERVAL_MS = 100;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  public powerDataList: Array<PowerData> = [];
  public annotationList: Array<AnnotationData> = [];
  public graph: Graph;
  public customScript: string;
  public halt = true;
  private inProgress = false;
  constructor(
    ui: Ui,
    servoController: ServoController,
    runner: TestRunner,
    configNum: number,
    customScript: string
  ) {
    this.ui = ui;
    this.graph = new Graph(ui, `graph${configNum}`);
    this.servoController = servoController;
    this.runner = runner;
    this.customScript = customScript;
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
  private async readDutLoop() {
    this.runner.executeCommand('\n');
    this.ui.addMessageToConsole('DutPort is selected');
    for (;;) {
      const dutData = await this.runner.readData();
      if (dutData.includes('start')) {
        this.annotationList.push([new Date().getTime(), 'start']);
        this.graph.addAnnotation(
          this.powerDataList[this.powerDataList.length - 1][0],
          'start'
        );
      } else if (dutData.includes('end')) {
        this.annotationList.push([new Date().getTime(), 'end']);
        this.graph.addAnnotation(
          this.powerDataList[this.powerDataList.length - 1][0],
          'end'
        );
      }
      this.ui.addMessageToConsole(dutData);
    }
  }
  public async start() {
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
    this.readDutLoop();
    await this.runner.copyScriptToDut(this.customScript);
    await this.runner.executeScript();
  }
  public async stop() {
    this.changeHaltFlag(true);
    this.inProgress = false;
  }
}
