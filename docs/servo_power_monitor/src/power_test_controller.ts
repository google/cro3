import {ServoController} from './servo_controller';
import {Graph} from './graph';
import {Histogram} from './histogram';
import {Ui} from './ui';
import {TestRunner} from './test_runner';

export type PowerData = [number, number];
export type AnnotationData = [number, string];
export class PowerTestController {
  private INTERVAL_MS = 100;
  public halt = true;
  private inProgress = false;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private powerDataList: Array<PowerData> = [];
  private annotationList: Array<AnnotationData> = [];
  private graph: Graph;
  private histogram = new Histogram();
  constructor(
    ui: Ui,
    graph: Graph,
    servoController: ServoController,
    runner: TestRunner
  ) {
    this.ui = ui;
    this.graph = graph;
    this.servoController = servoController;
    this.runner = runner;
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
    // await this.runner.executeCommand('\n');
    while (!this.halt) {
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
      } else if (dutData.includes('stop')) {
        this.stopMeasurement();
        break;
      }
      this.ui.addMessageToConsole(dutData);
    }
  }
  public async startMeasurement() {
    await this.runner.setScript();
    await this.servoController.servoShell.open();
    await this.runner.openDutPort();
    this.changeHaltFlag(false);
    this.readDutLoop();
    this.kickWriteLoop();
    this.readLoop();
    await this.runner.copyScriptToDut();
    await this.runner.executeScript();
  }
  public async stopMeasurement() {
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.servoController.servoShell.close();
    await this.runner.closeDutPort();
  }
  public analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.returnXrange();
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.powerDataList);
  }
  public loadPowerData(s: string) {
    const data = JSON.parse(s);
    this.powerDataList = data.power.map((d: {time: number; power: number}) => [
      d.time,
      d.power,
    ]);
    this.annotationList = data.annotation.map(
      (d: {text: string; time: number}) => [d.time, d.text]
    );
    this.graph.updateGraph(this.powerDataList);
    this.graph.findAnnotationPoint(this.powerDataList, this.annotationList);
  }
  public exportPowerData() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify({
          power: this.powerDataList.map(d => {
            return {time: d[0], power: d[1]};
          }),
          annotation: this.annotationList.map(d => {
            return {time: d[0], text: d[1]};
          }),
        })
      );
    return dataStr;
  }
  public setupDisconnectEvent() {
    // event when you disconnect serial port
    navigator.serial.addEventListener('disconnect', async () => {
      if (!this.halt) {
        this.changeHaltFlag(true);
        this.inProgress = false;
        await this.servoController.servoShell.close();
        await this.runner.dut.close();
      }
    });
  }
}
