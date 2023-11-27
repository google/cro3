import {ServoController} from './servo_controller';
import {Ui} from './ui';
import {TestRunner} from './test_runner';
import {Config} from './config';
import {TotalHistogram} from './total_histogram';

export type PowerData = [number, number];
export type AnnotationDataList = Map<string, number>;

export class PowerTestController {
  private marginTime = 300;
  private ui: Ui;
  private servoController: ServoController;
  private runner: TestRunner;
  private totalHistogram = new TotalHistogram();
  private configList: Array<Config> = [];
  private currentConfigNum = 0;
  private iterationNumber = 2;
  public isMeasuring = false;
  constructor(ui: Ui, servoController: ServoController, runner: TestRunner) {
    this.ui = ui;
    this.servoController = servoController;
    this.runner = runner;
  }

  public setConfig() {
    const shellScriptContents = this.ui.readInputShellScript();
    this.ui.createGraphList();
    for (let i = 0; i < this.ui.configNumber; i++) {
      const newConfig = new Config(
        this.ui,
        this.servoController,
        this.runner,
        i,
        shellScriptContents[i]
      );
      this.configList.push(newConfig);
    }
  }
  public async initializePort() {
    await this.servoController.servoShell.open();
    await this.servoController.servoShell.close();
    await this.runner.dut.open();
    await this.runner.sendCancel();
    await this.runner.sendCancel();
    await this.runner.sendCancel();
    await this.runner.dut.close();
  }
  public async startMeasurement() {
    if (this.ui.configNumber === 0) return;
    this.marginTime = Number(this.ui.marginTimeInput.value);
    this.iterationNumber = parseInt(this.ui.iterationInput.value);
    if (this.iterationNumber <= 0) return;
    await this.servoController.servoShell.select();
    await this.runner.dut.select();
    await this.initializePort();
    await this.setConfig();
    for (let i = 0; i < this.iterationNumber; i++) {
      this.ui.currentIteration.innerText = `${i + 1}`;
      for (let j = 0; j < this.ui.configNumber; j++) {
        this.currentConfigNum = j;
        console.log(`start running config${j}`);
        await this.configList[j].start();
      }
    }
    this.drawTotalHistogram();
    this.ui.hideElement(this.ui.currentIteration);
    this.ui.appendItrSelectors(this.iterationNumber, this.iterationNumber - 1);
  }
  public async stopMeasurement() {
    await this.configList[this.currentConfigNum].stop();
  }
  private drawTotalHistogram() {
    const histogramData = [];
    for (const config of this.configList) {
      const extractedData = config.extractTotalHistogramData(this.marginTime);
      histogramData.push(extractedData);
    }
    this.totalHistogram.paintHistogram(histogramData);
  }
  public showSelectedItrGraph(selectedIteration: number) {
    for (let i = 0; i < this.ui.configNumber; i++) {
      this.configList[i].loadGraph(selectedIteration);
    }
  }
  public loadPowerData(s: string) {
    const jsonData = JSON.parse(s);
    this.marginTime = jsonData.margin;
    this.ui.configNumber = jsonData.data.length;
    this.ui.createGraphList();
    this.configList = [];
    this.ui.appendItrSelectors(this.iterationNumber, 0);
    for (let i = 0; i < jsonData.data.length; i++) {
      const configData = jsonData.data[i];
      const newConfig = new Config(
        this.ui,
        this.servoController,
        this.runner,
        i,
        configData.config
      );
      configData.measuredData.map(
        (iterationData: {
          power: Array<{time: number; power: number}>;
          annotation: AnnotationDataList;
        }) => {
          const newPowerDataList = iterationData.power.map(
            (d: {time: number; power: number}) => [d.time, d.power] as PowerData
          );
          const newAnnotationList = new Map(
            Object.entries(iterationData.annotation)
          );
          newConfig.appendIterationDataList(
            newPowerDataList,
            newAnnotationList
          );
        }
      );
      newConfig.loadGraph(0);
      this.ui.loadConfigInputArea(configData.config);
      this.configList.push(newConfig);
    }
    this.drawTotalHistogram();
  }
  public exportPowerData() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify({
          margin: this.marginTime,
          iterationNum: this.iterationNumber,
          data: this.configList.map(config => ({
            config: config.customScript,
            measuredData: config.exportIterationDataList(),
          })),
        })
      );
    return dataStr;
  }
  public setupDisconnectEvent() {
    // event when you disconnect serial port
    navigator.serial.addEventListener('disconnect', async () => {
      if (this.isMeasuring) {
        this.isMeasuring = false;
        await this.servoController.closeServoPort();
        await this.runner.closeDutPort();
      }
    });
  }
}
