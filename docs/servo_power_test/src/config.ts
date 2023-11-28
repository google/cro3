import {Graph} from './graph';
import {AnnotationDataList, PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {TestRunner} from './test_runner';
import {Ui} from './ui';

export class IterationData {
  private powerDataList: Array<PowerData>;
  private annotationList: AnnotationDataList;
  private graph: Graph;
  constructor(
    powerDataList: Array<PowerData>,
    annotationList: AnnotationDataList,
    graph: Graph
  ) {
    this.powerDataList = powerDataList;
    this.annotationList = annotationList;
    this.graph = graph;
  }
  public appendPowerData(powerData: PowerData) {
    this.powerDataList.push(powerData);
  }
  public updateGraph() {
    this.graph.updateGraph(this.powerDataList);
  }
  public addAnnotation(label: string) {
    this.annotationList.set(label, new Date().getTime());
    this.graph.addAnnotation(
      this.powerDataList[this.powerDataList.length - 1][0],
      label
    );
  }
  public findAnnotation() {
    this.graph.findAnnotationPoint(this.powerDataList, this.annotationList);
  }
  public exportData() {
    return {
      power: this.powerDataList.map(d => {
        return {time: d[0], power: d[1]};
      }),
      annotation: Object.fromEntries(this.annotationList),
    };
  }
  public extractData(marginTime: number) {
    let startIndex = 0,
      endIndex = 0;
    for (let i = 0; i < this.powerDataList.length; i++) {
      if (
        this.annotationList.get('start')! + marginTime <=
        this.powerDataList[i][0]
      ) {
        startIndex = i;
        break;
      }
    }
    for (let i = this.powerDataList.length - 1; i >= 0; i--) {
      if (
        this.powerDataList[i][0] <=
        this.annotationList.get('end')! - marginTime
      ) {
        endIndex = i;
        break;
      }
    }
    return this.powerDataList.slice(startIndex, endIndex + 1).map(d => d[1]);
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
  private graph: Graph;
  private currentIteration: IterationData;
  public customScript: string;
  constructor(
    ui: Ui,
    servoController: ServoController,
    runner: TestRunner,
    configNumber: number,
    customScript: string
  ) {
    this.ui = ui;
    this.graph = new Graph(
      ui,
      document.getElementById(`graph${configNumber}`) as HTMLDivElement
    );
    this.servoController = servoController;
    this.runner = runner;
    this.customScript = customScript;
    this.currentIteration = new IterationData(
      [],
      new Map<string, number>(),
      this.graph
    );
  }
  public appendIterationDataList(
    newPowerDataList: Array<PowerData>,
    newAnnotationList: AnnotationDataList
  ) {
    this.iterationDataList.push(
      new IterationData(newPowerDataList, newAnnotationList, this.graph)
    );
  }
  public exportIterationDataList() {
    return this.iterationDataList.map(iterationData =>
      iterationData.exportData()
    );
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
      this.currentIteration.appendPowerData(e);
      this.currentIteration.updateGraph();
    }
  }
  private async readDutLoop() {
    while (!this.halt) {
      const dutData = await this.runner.readData();
      try {
        if (dutData.includes('start')) {
          this.currentIteration.addAnnotation('start');
        } else if (dutData.includes('end')) {
          this.currentIteration.addAnnotation('end');
        } else if (dutData.includes('stop')) {
          await this.stop();
        }
      } catch (e) {
        console.error(e);
        throw e;
      } finally {
        this.ui.addMessageToConsole(dutData);
      }
    }
  }
  public async start() {
    this.currentIteration = new IterationData(
      [],
      new Map<string, number>(),
      this.graph
    );
    await this.runner.openDutPort();
    await this.servoController.openServoPort();
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
    const readDutLoopPromise = this.readDutLoop();
    await this.runner.runWorkload(this.customScript);
    await this.runner.executeScript();
    await readDutLoopPromise;
    this.iterationDataList.push(this.currentIteration);
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
  public loadGraph(selectedIteration: number) {
    this.iterationDataList[selectedIteration].updateGraph();
    this.iterationDataList[selectedIteration].findAnnotation();
  }
}
