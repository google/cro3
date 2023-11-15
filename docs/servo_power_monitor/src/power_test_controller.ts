import {ServoController} from './servo_controller';
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
  private histogram = new Histogram();
  private configList: Array<Config> = [];
  private currentConfigNum = 0;
  public isMeasuring = false;
  constructor(ui: Ui, servoController: ServoController, runner: TestRunner) {
    this.ui = ui;
    this.servoController = servoController;
    this.runner = runner;
  }

  public setConfig() {
    const shellScriptContents = this.ui.readInputShellScript();
    for (let i = 0; i < this.ui.configNum; i++) {
      const newConfig = new Config(
        this.ui,
        this.servoController,
        this.runner,
        i + 1,
        shellScriptContents[i]
      );
      this.configList.push(newConfig);
    }
  }
  public async startMeasurement() {
    await this.servoController.servoShell.select();
    await this.runner.dut.select();
    await this.setConfig();
    for (let i = 0; i < this.ui.configNum; i++) {
      this.currentConfigNum = i;
      console.log(`start running config${i}`);
      await this.configList[i].start();
    }
  }
  public async stopMeasurement() {
    await this.configList[this.currentConfigNum].stop();
  }
  // public analyzePowerData() {
  //   // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
  //   const xrange = this.graph.returnXrange();
  //   const left = xrange[0];
  //   const right = xrange[1];
  //   this.histogram.paintHistogram(left, right, this.powerDataList);
  // }
  public loadPowerData(s: string) {
    const data = JSON.parse(s);
    this.configList = [];
    for (let i = 0; i < data.length; i++) {
      this.ui.addConfigInputArea();
      const configData = data[i];
      const newConfig = new Config(
        this.ui,
        this.servoController,
        this.runner,
        i + 1,
        configData.config
      );
      newConfig.powerDataList = configData.power.map(
        (d: {time: number; power: number}) => [d.time, d.power]
      );
      newConfig.annotationList = configData.annotation.map(
        (d: {text: string; time: number}) => [d.time, d.text]
      );
      newConfig.graph.updateGraph(newConfig.powerDataList);
      newConfig.graph.findAnnotationPoint(
        newConfig.powerDataList,
        newConfig.annotationList
      );
      this.configList.push(newConfig);
    }
  }
  public exportPowerData() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          this.configList.map(e => ({
            config: e.customScript,
            power: e.powerDataList.map(d => {
              return {time: d[0], power: d[1]};
            }),
            annotation: e.annotationList.map(d => {
              return {time: d[0], text: d[1]};
            }),
          }))
        )
      );
    return dataStr;
  }
  public setupDisconnectEvent() {
    // event when you disconnect serial port
    navigator.serial.addEventListener('disconnect', async () => {
      if (this.isMeasuring) {
        this.isMeasuring = false;
        await this.servoController.closeServoPort();
      }
    });
  }
}
