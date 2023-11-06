import {ServoController} from './servoController';
import {Graph} from './graph';
import {Histogram} from './histogram';

export class PowerTestController {
  private INTERVAL_MS = 100;
  public halt = true;
  private inProgress = false;
  private servoController: ServoController;
  private powerData: Array<Array<Date | number>> = [];
  private graph = new Graph();
  private histogram = new Histogram();
  private enabledRecordingButton: (flag: boolean) => void;
  private setSerialOutput: (s: string) => void;
  constructor(
    servoController: ServoController,
    enabledRecordingButton: (flag: boolean) => void,
    setSerialOutput: (s: string) => void
  ) {
    this.servoController = servoController;
    this.enabledRecordingButton = enabledRecordingButton;
    enabledRecordingButton(true);
    this.setSerialOutput = setSerialOutput;
  }
  private changeHaltFlag(flag: boolean) {
    this.halt = flag;
    this.enabledRecordingButton(flag);
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
      if (currentPowerData === undefined) continue;
      this.setSerialOutput(currentPowerData.originalData);
      const e: Array<Date | number> = [new Date(), currentPowerData.power];
      this.powerData.push(e);
      this.graph.updateGraph(this.powerData);
    }
  }
  public async startMeasurement(isSerial: boolean) {
    await this.servoController.servoShell.open(isSerial);
    this.changeHaltFlag(false);
    this.kickWriteLoop();
    this.readLoop();
  }
  public async stopMeasurement() {
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.servoController.servoShell.close();
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
    this.powerData = data.power.map((d: string) => [new Date(d[0]), d[1]]);
    this.graph.updateGraph(this.powerData);
  }
  public exportPowerData() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: this.powerData}));
    return dataStr;
  }
  public setupDisconnectEvent() {
    // `disconnect` event is fired when a Usb device is disconnected.
    // c.f. https://wicg.github.io/webusb/#disconnect (5.1. Events)
    navigator.usb.addEventListener('disconnect', () => {
      if (!this.halt && !this.servoController.servoShell.isSerial) {
        //  No need to call close() for the Usb servoPort here because the
        //  specification says that
        // the servoPort will be closed automatically when a device is disconnected.
        this.changeHaltFlag(true);
        this.inProgress = false;
        this.enabledRecordingButton(this.halt);
      }
    });
    // event when you disconnect serial port
    navigator.serial.addEventListener('disconnect', async () => {
      if (!this.halt && this.servoController.servoShell.isSerial) {
        await this.servoController.servoShell.close();
        this.changeHaltFlag(true);
        this.inProgress = false;
        this.enabledRecordingButton(this.halt);
      }
    });
  }
}
