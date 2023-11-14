import {ServoController} from './servo_controller';
import {Graph} from './graph';
import {Histogram} from './histogram';
import {Ui} from './ui';
import {TestRunner} from './test_runner';
import {Config} from './config';

export type PowerData = [number, number];
export type AnnotationData = [number, string];

export class PowerTestController {
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private powerDataList: Array<PowerData> = [];
  private annotationList: Array<AnnotationData> = [];
  private graph: Graph;
  private histogram = new Histogram();
  private configList: Array<Config> = [];
  private currentConfigNum = 0;
  private isMeasuresing = false;
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

  public setConfig() {
    const shellScriptContents = this.ui.readInputShellScript();
    for (let i = 0; i < this.ui.configNum; i++) {
      const newConfig = new Config(
        this.ui,
        this.graph,
        this.servoController,
        this.runner,
        shellScriptContents[i]
      );
      this.configList.push(newConfig);
    }
    console.log(this.configList);
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
  public async startMeasurement() {
    await this.setConfig();
    await this.servoController.servoShell.open();
    for (let i = 0; i < this.ui.configNum; i++) {
      this.configList[i].start();
      this.currentConfigNum = i;
    }
  }
  public async stopMeasurement() {
    await this.configList[this.currentConfigNum].stop();
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
      if (this.isMeasuresing) {
        this.isMeasuresing = false;
        await this.servoController.servoShell.close();
      }
    });
  }
}
