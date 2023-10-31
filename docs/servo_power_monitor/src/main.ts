import {powerGraph} from './graph';
import {histogram} from './histogram';
import {serialPort} from './serialport';
import {
  addMessageToConsole,
  addServoConsole,
  closePopup,
  enabledRecordingButton,
  readInputValue,
  setDownloadAnchor,
} from './ui';
import {usbPort} from './usbport';

export class powerMonitor {
  INTERVAL_MS = 100;
  CANCEL_CMD = '\x03\n';
  // shell script
  scripts = `#!/bin/bash -e
function workload () {
  ectool chargecontrol idle
  stress-ng -c 1 -t \\$1
  echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;
  halt = false;
  inProgress = false;
  isSerial = false;
  isDutOpened = false;
  graph = new powerGraph();
  histogram = new histogram();
  output = '';
  usb = new usbPort();
  servo = new serialPort();
  dut = new serialPort();

  pushOutput = (s: string) => {
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
  };
  kickWriteLoop = (writeFn: (s: string) => Promise<void>) => {
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
  };
  readLoop = async (readFn: () => Promise<string>) => {
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
  };
  selectDutSerial = async () => {
    await this.dut.open(0x18d1, 0x504a);
    this.isDutOpened = true;
    addMessageToConsole('DutPort is selected');
    for (;;) {
      const chunk = await this.dut.read();
      addMessageToConsole(chunk);
    }
  };
  formSubmit = async (e: Event) => {
    e.preventDefault();
    if (!this.isDutOpened) {
      closePopup();
      return;
    }
    await this.dut.write(readInputValue() + '\n');
  };
  // send cancel command to serial port when ctrl+C is pressed in input area
  cancelSubmit = async (e: KeyboardEvent) => {
    if (!this.isDutOpened) {
      closePopup();
      return;
    }
    if (e.ctrlKey && e.key === 'c') {
      await this.dut.write(this.CANCEL_CMD);
    }
  };
  executeScript = async () => {
    if (!this.isDutOpened) {
      closePopup();
    } else {
      await this.dut.write('cat > ./example.sh << EOF\n');
      await this.dut.write(this.scripts);
      await this.dut.write('EOF\n');
      await this.dut.write('bash ./example.sh\n');
    }
  };
  requestUsb = async () => {
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
  };
  requestSerial = async () => {
    this.halt = false;
    await this.servo.open(0x18d1, 0x520d);
    this.isSerial = true;
    enabledRecordingButton(this.halt);
    await this.servo.write('help\n');
    // TODO: Implement something to check the validity of servo serial port

    this.kickWriteLoop(async s => this.servo.write(s));
    this.readLoop(() => this.servo.read());
  };
  disconnectUsbPort = async () => {
    if (!this.halt && !this.isSerial) {
      //  No need to call close() for the Usb servoPort here because the
      //  specification says that
      // the servoPort will be closed automatically when a device is disconnected.
      this.halt = true;
      this.inProgress = false;
      enabledRecordingButton(this.halt);
    }
  };
  disconnectSerialPort = async () => {
    if (!this.halt && this.isSerial) {
      await this.servo.close();
      this.halt = true;
      this.inProgress = false;
      enabledRecordingButton(this.halt);
    }
    if (this.isDutOpened) {
      await this.dut.close();
      this.isDutOpened = false;
    }
  };
  stopMeasurement = async () => {
    this.halt = true;
    this.inProgress = false;
    if (this.isSerial) {
      await this.servo.close();
    } else {
      await this.usb.close();
    }
    enabledRecordingButton(this.halt);
  };
  analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.g.xAxisRange();
    console.log(this.graph.g.xAxisExtremes());
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.graph.powerData);
  }
  downloadJSONFile = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: this.graph.powerData}));
    setDownloadAnchor(dataStr);
  };
  handleFileSelect = (evt: DragEvent) => {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    const file = eventDataTransfer.files[0];
    if (file === undefined) {
      return;
    }
    const r = new FileReader();
    r.addEventListener('load', () => {
      const data = JSON.parse(r.result as string);
      this.graph.updateData(
        data.power.map((d: string) => [new Date(d[0]), d[1]])
      );
      this.graph.updateGraph();
    });
    r.readAsText(file);
  };
  handleDragOver = (evt: DragEvent) => {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
  };
}
