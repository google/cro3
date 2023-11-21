import {Graph} from './graph';
import {AnnotationDataList, PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {TestRunner} from './test_runner';
import {Ui} from './ui';

export class Config {
  private INTERVAL_MS = 100;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private halt = true;
  private inProgress = false;
  public powerDataList: Array<PowerData> = [];
  public annotationList: AnnotationDataList = new Map<string, number>();
  public graph: Graph;
  public customScript: string;
  constructor(
    ui: Ui,
    servoController: ServoController,
    runner: TestRunner,
    configNum: number,
    customScript: string
  ) {
    this.ui = ui;
    this.graph = new Graph(
      ui,
      document.getElementById(`graph${configNum}`) as HTMLDivElement
    );
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
    while (!this.halt) {
      const dutData = await this.runner.readData();
      try {
        if (dutData.includes('start')) {
          this.annotationList.set('start', new Date().getTime());
          this.graph.addAnnotation(
            this.powerDataList[this.powerDataList.length - 1][0],
            'start'
          );
        } else if (dutData.includes('end')) {
          this.annotationList.set('end', new Date().getTime());
          this.graph.addAnnotation(
            this.powerDataList[this.powerDataList.length - 1][0],
            'end'
          );
        } else if (dutData.includes('stop')) {
          await this.stop();
        }
      } catch (e) {
        console.error(e);
        throw e;
      } finally {
        await this.ui.addMessageToConsole(dutData);
      }
    }
  }
  public async start() {
    await this.runner.openDutPort();
    await this.servoController.openServoPort();
    await this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
    const readDutLoopPromise = this.readDutLoop();
    await this.runner.copyScriptToDut(this.customScript);
    await this.runner.executeScript();
    await readDutLoopPromise;
  }
  public async stop() {
    await this.runner.sendCancel();
    await this.runner.sendCancel();
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.servoController.closeServoPort();
    await this.runner.closeDutPort();
  }
}
