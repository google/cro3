import {powerGraph} from './powerGraph';
import {operatePort} from './operatePort';
import {histogram} from './histogram';

export class dataRecoder {
  INTERVAL_MS = 100;
  halt = false;
  inProgress = false;
  enabledRecordingButton: (flag: boolean) => void;
  graph = new powerGraph();
  histogram = new histogram();
  output = '';
  powerData: Array<Array<Date | number>> = [];
  servoShell: operatePort;
  setSerialOutput: (s: string) => void;
  constructor(
    servoShell: operatePort,
    enabledRecordingButton: (flag: boolean) => void,
    setSerialOutput: (s: string) => void
  ) {
    this.servoShell = servoShell;
    this.enabledRecordingButton = enabledRecordingButton;
    this.setSerialOutput = setSerialOutput;
  }
  changeHaltFlag(flag: boolean) {
    this.halt = flag;
  }
  pushData(s: string) {
    this.output += s;

    const splitted = this.output.split('\n').filter(s => s.trim().length > 10);
    if (
      splitted.length > 0 &&
      splitted[splitted.length - 1].indexOf('Alert limit') >= 0
    ) {
      const powerString = splitted.find(s => s.startsWith('Power'));
      if (powerString === undefined) return;
      const power = parseInt(powerString.split('=>')[1].trim().split(' ')[0]);
      const e: Array<Date | number> = [new Date(), power];
      this.powerData.push(e);
      this.graph.updateGraph(this.powerData);
      this.setSerialOutput(this.output);
      this.output = '';
      this.inProgress = false;
    }
  }
  private kickWriteLoop(writeFn: (s: string) => Promise<void>) {
    const f = async () => {
      while (!this.halt) {
        if (this.inProgress) {
          console.error('previous request is in progress! skip...');
        } else {
          this.inProgress = true;
        }

        // ina 0 and 1 seems to be the same
        // ina 2 is something but not useful
        const cmd = 'ina 0\n';
        await writeFn(cmd);
        await new Promise(r => setTimeout(r, this.INTERVAL_MS));
      }
    };
    setTimeout(f, this.INTERVAL_MS);
  }
  private async readLoop(readFn: () => Promise<string>) {
    while (!this.halt) {
      try {
        const s = await readFn();
        if (s === '' || !s.length) {
          continue;
        }
        this.pushData(s);
      } catch (e) {
        // break the loop here because `disconnect` event is not called in Chrome
        // for some reason when the loop continues. And no need to throw error
        // here because it is thrown in readFn.
        break;
      }
    }
  }
  async start() {
    this.changeHaltFlag(false);
    await this.servoShell.open();
    // this.enabledRecordingButton(this.halt);
    // TODO: Implement something to check the validity of servo serial servoShell
    // await this.servo.write('help\n');
    this.kickWriteLoop(async s => this.servoShell.write(s));
    this.readLoop(() => this.servoShell.read());
  }
  async stop() {
    this.changeHaltFlag(true);
    this.inProgress = false;
    await this.servoShell.close();
    // this.enabledRecordingButton(this.halt);
  }
  analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.g.xAxisRange();
    console.log(this.graph.g.xAxisExtremes());
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.powerData);
  }
  readJsonFile(s: string) {
    const data = JSON.parse(s);
    this.powerData = data.power.map((d: string) => [new Date(d[0]), d[1]]);
    this.graph.updateGraph(this.powerData);
  }
  writeJsonFile() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: this.powerData}));
    return dataStr;
  }
  setupDisconnectEvent() {
    // `disconnect` event is fired when a Usb device is disconnected.
    // c.f. https://wicg.github.io/webusb/#disconnect (5.1. Events)
    navigator.usb.addEventListener('disconnect', () => {
      if (!this.halt && !this.servoShell.isSerial) {
        //  No need to call close() for the Usb servoPort here because the
        //  specification says that
        // the servoPort will be closed automatically when a device is disconnected.
        this.changeHaltFlag(true);
        this.inProgress = false;
        // this.enabledRecordingButton(this.halt);
      }
    });
    // event when you disconnect serial port
    navigator.serial.addEventListener('disconnect', async () => {
      if (!this.halt && this.servoShell.isSerial) {
        await this.servoShell.close();
        this.changeHaltFlag(true);
        this.inProgress = false;
        // this.enabledRecordingButton(this.halt);
      }
    });
  }
}
