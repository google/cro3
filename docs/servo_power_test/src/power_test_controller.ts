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
  private currentConfigNumber = 0;
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
  private async readAllDutBuffer() {
    console.log('start reading');
    const racePromise = Promise.race([
      this.runner.readData(),
      new Promise((_, reject) => setTimeout(reject, 1000)),
    ]);
    try {
      await racePromise;
      // this.runner.readData() is resolved faster
      // that is, some data is read in 1000ms
      console.log('data is left');
      return false;
    } catch {
      // setTimeOut() is resolved faster
      // that is, no data is read in 1000ms
      console.log('all data is read');
      return true;
    }
  }
  private async initialize() {
    await this.servoController.servoShell.open();
    await this.servoController.servoShell.close();
    await this.runner.dut.open();
    await this.runner.sendCancel();
    await this.runner.sendCancel();
    await this.runner.sendCancel();
    for (;;) {
      const allDataIsRead = await this.readAllDutBuffer();
      if (allDataIsRead) {
        // all data is read from DUT
        break;
      }
    }
    await this.runner.dut.close();
  }
  private async finalize() {
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
    await this.initialize();
    await this.setConfig();
    for (let i = 0; i < this.iterationNumber; i++) {
      this.ui.currentIteration.innerText = `${i + 1}`;
      for (let j = 0; j < this.ui.configNumber; j++) {
        this.currentConfigNumber = j;
        console.log(`start running config${j}`);
        await this.configList[j].start();
      }
    }
    this.finalize();
    this.drawTotalHistogram();
    this.ui.hideElement(this.ui.currentIteration);
    this.ui.appendIterationSelectors(
      this.iterationNumber,
      this.iterationNumber - 1
    );
  }
  public async stopMeasurement() {
    await this.configList[this.currentConfigNumber].stop();
  }
  private drawTotalHistogram() {
    const histogramData = [];
    for (const config of this.configList) {
      const extractedData = config.extractTotalHistogramData(this.marginTime);
      histogramData.push(extractedData);
    }
    this.totalHistogram.paintHistogram(histogramData);
  }
  public showSelectedIterationGraph(selectedIteration: number) {
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
    this.ui.appendIterationSelectors(this.iterationNumber, 0);
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
          iterationNumber: this.iterationNumber,
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
        this.finalize();
        await this.servoController.closeServoPort();
        await this.runner.closeDutPort();
      }
    });
  }
}
