import {powerGraph} from './graph';
import {histogram} from './histogram';
import {serialPort} from './serialport';
import {addServoConsole, enabledRecordingButton, setDownloadAnchor} from './ui';
import {usbPort} from './usbport';

export class powerMonitor {
  INTERVAL_MS = 100;
  halt = false;
  inProgress = false;
  isSerial = false;
  graph: powerGraph;
  histogram = new histogram();
  output = '';
  usb = new usbPort();
  servo = new serialPort();
  constructor(graph: powerGraph) {
    this.graph = graph;
  }
  pushOutput(s: string) {
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
      this.graph.pushData(e);
      this.graph.updateGraph();
      addServoConsole(this.output);
      this.output = '';
      this.inProgress = false;
    }
  }
  kickWriteLoop(writeFn: (s: string) => Promise<void>) {
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
  async readLoop(readFn: () => Promise<string>) {
    while (!this.halt) {
      try {
        const s = await readFn();
        if (s === '' || !s.length) {
          continue;
        }
        this.pushOutput(s);
      } catch (e) {
        // break the loop here because `disconnect` event is not called in Chrome
        // for some reason when the loop continues. And no need to throw error
        // here because it is thrown in readFn.
        break;
      }
    }
  }

  async requestUsb() {
    this.halt = false;
    await this.usb.open();
    this.isSerial = false;
    enabledRecordingButton(this.halt);
    try {
      this.kickWriteLoop(async s => this.usb.write(s));
      this.readLoop(async () => this.usb.read(this.halt));
    } catch (err) {
      console.error(`Disconnected: ${err}`);
      this.halt = true;
      enabledRecordingButton(this.halt);
    }
  }
  async requestSerial() {
    this.halt = false;
    await this.servo.open(0x18d1, 0x520d);
    this.isSerial = true;
    enabledRecordingButton(this.halt);
    await this.servo.write('help\n');
    // TODO: Implement something to check the validity of servo serial port

    this.kickWriteLoop(async s => this.servo.write(s));
    this.readLoop(() => this.servo.read());
  }
  disconnectUsbPort() {
    if (!this.halt && !this.isSerial) {
      //  No need to call close() for the Usb servoPort here because the
      //  specification says that
      // the servoPort will be closed automatically when a device is disconnected.
      this.halt = true;
      this.inProgress = false;
      enabledRecordingButton(this.halt);
    }
  }
  async disconnectSerialPort() {
    if (!this.halt && this.isSerial) {
      await this.servo.close();
      this.halt = true;
      this.inProgress = false;
      enabledRecordingButton(this.halt);
    }
  }
  async stopMeasurement() {
    this.halt = true;
    this.inProgress = false;
    if (this.isSerial) {
      await this.servo.close();
    } else {
      await this.usb.close();
    }
    enabledRecordingButton(this.halt);
  }
  analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.g.xAxisRange();
    console.log(this.graph.g.xAxisExtremes());
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.graph.powerData);
  }
  downloadJSONFile() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: this.graph.powerData}));
    setDownloadAnchor(dataStr);
  }
}
