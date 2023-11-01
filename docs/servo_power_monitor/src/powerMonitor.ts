import {powerGraph} from './graph';
import {serialPort} from './serialport';
import {usbPort} from './usbport';

export class powerMonitor {
  INTERVAL_MS = 100;
  halt = false;
  inProgress = false;
  isSerial = false;
  graph: powerGraph;
  output = '';
  usb = new usbPort(this.halt);
  servo = new serialPort();
  requestUsbButton = document.getElementById(
    'request-device'
  ) as HTMLButtonElement;
  requestSerialButton = document.getElementById(
    'requestSerialButton'
  ) as HTMLButtonElement;
  haltButton = document.getElementById('haltButton') as HTMLButtonElement;
  serial_output = document.getElementById('serial_output') as HTMLDivElement;

  constructor(graph: powerGraph) {
    this.graph = graph;
  }
  enabledRecordingButton(halt: boolean) {
    this.requestUsbButton.disabled = !halt;
    this.requestSerialButton.disabled = !halt;
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
      this.serial_output.textContent = this.output;
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
    this.enabledRecordingButton(this.halt);
    try {
      this.kickWriteLoop(async s => this.usb.write(s));
      this.readLoop(async () => this.usb.read());
    } catch (err) {
      console.error(`Disconnected: ${err}`);
      this.halt = true;
      this.enabledRecordingButton(this.halt);
    }
  }
  async requestSerial() {
    this.halt = false;
    await this.servo.open(0x18d1, 0x520d);
    this.isSerial = true;
    this.enabledRecordingButton(this.halt);
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
      this.enabledRecordingButton(this.halt);
    }
  }
  async disconnectSerialPort() {
    if (!this.halt && this.isSerial) {
      await this.servo.close();
      this.halt = true;
      this.inProgress = false;
      this.enabledRecordingButton(this.halt);
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
    this.enabledRecordingButton(this.halt);
  }
  setupHtmlEvent() {
    this.requestSerialButton.addEventListener('click', () =>
      this.requestSerial()
    );
    this.requestUsbButton.addEventListener('click', () => this.requestUsb());
    this.haltButton.addEventListener('click', () => this.stopMeasurement());
  }
}
