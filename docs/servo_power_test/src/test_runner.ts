import {Graph} from './graph';
import {AnnotationDataList, PowerData} from './power_test_controller';
import {ServoController} from './servo_controller';
import {DutController} from './dut_controller';
import {Ui} from './ui';

export class IterationData {
  private powerDataList: Array<PowerData>;
  private annotationList: AnnotationDataList;
  private histogramDataList: Array<number>;
  private graph: Graph;
  private isWorkloadRunning = false;
  private powerSum: number;
  private powerAverage: number;
  constructor(
    powerDataList: Array<PowerData>,
    annotationList: AnnotationDataList,
    histogramDataList: Array<number>,
    graph: Graph
  ) {
    this.powerDataList = powerDataList;
    this.annotationList = annotationList;
    this.histogramDataList = histogramDataList;
    this.graph = graph;
    this.graph.clearHistogram();
    this.powerSum = this.sumPowerData();
    this.powerAverage = this.averagePowerData();
  }
  public setIsWorkloadRunning(flag: boolean) {
    this.isWorkloadRunning = flag;
  }
  public sumPowerData() {
    let powerSum = 0;
    this.histogramDataList.forEach(powerData => {
      powerSum += powerData;
    });
    return powerSum;
  }
  public averagePowerData() {
    if (this.histogramDataList.length === 0) {
      return 0;
    }
    return this.powerSum / this.histogramDataList.length;
  }
  public setExtractTime(marginTime: number) {
    const startExtractTime = this.annotationList.get('start')! + marginTime;
    const endExtractTime = this.annotationList.get('end')! - marginTime;
    this.graph.setExtractTime(startExtractTime, endExtractTime);
  }
  public appendPowerData(powerData: PowerData) {
    this.powerDataList.push(powerData);
    if (this.isWorkloadRunning) {
      this.histogramDataList.push(powerData[1]);
      this.powerSum += powerData[1];
      this.powerAverage = this.averagePowerData();
    }
  }
  public appendHistogramData(power: number) {
    this.histogramDataList.push(power);
  }
  public updateGraph() {
    this.graph.updateGraph(this.powerDataList, this.powerAverage);
    if (this.isWorkloadRunning) {
      this.graph.updateHistogram(this.histogramDataList);
    }
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
  public loadHistogramData() {
    this.histogramDataList = this.extractData(0);
    this.powerSum = this.sumPowerData();
    this.powerAverage = this.averagePowerData();
  }
}

export class TestRunner {
  private INTERVAL_MS = 100;
  private ui: Ui;
  private servoController: ServoController;
  private dutController: DutController;
  private halt = true;
  private inProgress = false;
  private iterationDataList: Array<IterationData> = [];
  private graph: Graph;
  private currentIteration: IterationData;
  private marginTime: number;
  public configScript: string;
  public cancelled = false;
  constructor(
    ui: Ui,
    servoController: ServoController,
    dutController: DutController,
    runnerNumber: number,
    configScript: string,
    marginTime: number
  ) {
    this.ui = ui;
    this.graph = new Graph(
      ui,
      document.getElementById(`graph${runnerNumber}`) as HTMLDivElement,
      document.getElementById(`histogram${runnerNumber}`) as HTMLDivElement
    );
    this.servoController = servoController;
    this.dutController = dutController;
    this.configScript = configScript;
    this.currentIteration = new IterationData(
      [],
      new Map<string, number>(),
      [],
      this.graph
    );
    this.marginTime = marginTime;
  }
  private setCurrentIteration(selectedIteration: number) {
    this.currentIteration = this.iterationDataList[selectedIteration];
  }
  public appendIterationDataList(
    newPowerDataList: Array<PowerData>,
    newAnnotationList: AnnotationDataList
  ) {
    const newIterationData = new IterationData(
      newPowerDataList,
      newAnnotationList,
      [],
      this.graph
    );
    newIterationData.loadHistogramData();
    this.iterationDataList.push(newIterationData);
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
      const dutData = await this.dutController.readData();
      try {
        if (dutData.includes('start')) {
          this.currentIteration.addAnnotation('start');
          this.currentIteration.setIsWorkloadRunning(true);
        } else if (dutData.includes('end')) {
          this.currentIteration.addAnnotation('end');
          this.currentIteration.setIsWorkloadRunning(false);
          this.currentIteration.setExtractTime(this.marginTime);
        } else if (dutData.includes('stop')) {
          await this.stop();
        }
      } catch (e) {
        console.error(e);
        await this.cancel();
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
      [],
      this.graph
    );
    await this.dutController.openDutPort();
    await this.servoController.openServoPort();
    await this.dutController.discardAllDutBuffer(100);
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
    const readDutLoopPromise = this.readDutLoop();
    await this.dutController.runWorkload(this.configScript);
    await readDutLoopPromise;
    this.iterationDataList.push(this.currentIteration);
  }
  public async stop() {
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.dutController.sendCancelCommand();
    await this.dutController.sendCancelCommand();
    await this.servoController.closeServoPort();
    await this.dutController.closeDutPort();
  }
  public async cancel() {
    try {
      this.stop();
    } catch (error) {
      console.error(error);
      throw error;
    } finally {
      this.cancelled = true;
    }
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
    this.setCurrentIteration(selectedIteration);
    this.currentIteration.setIsWorkloadRunning(true);
    this.currentIteration.setExtractTime(this.marginTime);
    this.currentIteration.updateGraph();
    this.currentIteration.findAnnotation();
  }
}
