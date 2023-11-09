import {ServoController} from './servo_controller';
import {Graph} from './graph';
import {Histogram} from './histogram';
import {Ui} from './ui';
import {TestRunner} from './test_runner';

export type PowerData = [Date, number];
export type AnnotationText = 'start' | 'end';
export type AnnotationData = [AnnotationText, Date];

export class PowerTestController {
  private INTERVAL_MS = 100;
  public halt = true;
  private inProgress = false;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private powerData: Array<PowerData> = [];
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
      const e: PowerData = [new Date(), currentPowerData.power];
      this.powerData.push(e);
      this.graph.updateGraph(this.powerData);
    }
  }
  private async readDutLoop() {
    this.ui.addMessageToConsole('DutPort is selected');
    for (;;) {
      const dutData = await this.runner.readData();
      if (dutData.includes('start')) {
        this.graph.setAnnotationFlag('start');
        this.annotationList.push(['start', new Date()]);
      } else if (dutData.includes('end')) {
        this.graph.setAnnotationFlag('end');
        this.annotationList.push(['end', new Date()]);
      }
      this.ui.addMessageToConsole(dutData);
    }
  }
  public async startMeasurement() {
    await this.servoController.servoShell.open();
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
  }
  public async stopMeasurement() {
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.servoController.servoShell.close();
  }
  public async selectPort() {
    await this.runner.dut.open();
    this.runner.isOpened = true;
    this.readDutLoop();
  }
  public analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.returnXrange();
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.powerData);
  }
  public loadPowerData(s: string) {
    const data = JSON.parse(s);
    console.log(data);
    this.powerData = data.power.map((d: {time: number; power: number}) => [
      new Date(d.time),
      d.power,
    ]);
    this.annotationList = data.power.map((d: {text: string; time: number}) => [
      d.text,
      new Date(d.time),
    ]);
    this.graph.updateGraph(this.powerData);
  }
  public exportPowerData() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify({
          power: this.powerData.map(d => {
            return {
              time: d[0].getTime(),
              power: d[1],
            };
          }),
          annotation: this.annotationList.map(d => {
            return {
              text: d[0],
              time: d[1].getTime(),
            };
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
      }
    });
  }
}
