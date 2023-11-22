import {Graph} from './graph';
import {AnnotationDataList, PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {TestRunner} from './test_runner';
import {Ui} from './ui';

export class IterationData {
  public powerDataList: Array<PowerData>;
  public annotationList: AnnotationDataList;
  constructor(
    powerDataList: Array<PowerData>,
    annotationList: AnnotationDataList
  ) {
    this.powerDataList = powerDataList;
    this.annotationList = annotationList;
  }
  public extractData(marginTime: number) {
    const extractedData = [];
    for (const powerData of this.powerDataList) {
      if (
        this.annotationList.get('start')! + marginTime <= powerData[0] &&
        powerData[0] <= this.annotationList.get('end')! - marginTime
      ) {
        extractedData.push(powerData[1]);
      }
    }
    return extractedData;
  }
}

export class Config {
  private INTERVAL_MS = 100;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private halt = true;
  private inProgress = false;
  private iterationDataList: Array<IterationData> = [];
  public graph: Graph;
  public customScript: string;
  public currentItrNum = 0;
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
  public appendIterationDataList(newIterationData: IterationData) {
    this.iterationDataList.push(newIterationData);
  }
  public exportIterationDataList() {
    return this.iterationDataList.map(iterationData => {
      return {
        power: iterationData.powerDataList.map(d => {
          return {time: d[0], power: d[1]};
        }),
        annotation: Object.fromEntries(iterationData.annotationList),
      };
    });
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
      this.iterationDataList[this.currentItrNum].powerDataList.push(e);
      this.graph.updateGraph(
        this.iterationDataList[this.currentItrNum].powerDataList
      );
    }
  }
  private async readDutLoop() {
    while (!this.halt) {
      const dutData = await this.runner.readData();
      try {
        if (dutData.includes('start')) {
          this.iterationDataList[this.currentItrNum].annotationList.set(
            'start',
            new Date().getTime()
          );
          this.graph.addAnnotation(
            this.iterationDataList[this.currentItrNum].powerDataList[
              this.iterationDataList[this.currentItrNum].powerDataList.length -
                1
            ][0],
            'start'
          );
        } else if (dutData.includes('end')) {
          this.iterationDataList[this.currentItrNum].annotationList.set(
            'end',
            new Date().getTime()
          );
          this.graph.addAnnotation(
            this.iterationDataList[this.currentItrNum].powerDataList[
              this.iterationDataList[this.currentItrNum].powerDataList.length -
                1
            ][0],
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
    this.iterationDataList.push(
      new IterationData([], new Map<string, number>())
    );
    await this.runner.openDutPort();
    await this.servoController.openServoPort();
    await this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
    const readDutLoopPromise = this.readDutLoop();
    if (this.currentItrNum === 0) {
      await this.runner.copyScriptToDut(this.customScript);
    }
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
  public extractTotalHistogramData(marginTime: number) {
    let extractedData: Array<number> = [];
    for (const iterationData of this.iterationDataList) {
      extractedData = extractedData.concat(
        iterationData.extractData(marginTime)
      );
    }
    return extractedData;
  }
  public loadGraph(selectedItr: number) {
    this.graph.updateGraph(this.iterationDataList[selectedItr].powerDataList);
    this.graph.findAnnotationPoint(
      this.iterationDataList[selectedItr].powerDataList,
      this.iterationDataList[selectedItr].annotationList
    );
  }
}
