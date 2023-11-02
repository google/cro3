import {dataRecoder} from './dataRecoder';
import {operatePort} from './operatePort';
import {testRunner} from './testRunner';

export class powerTestController {
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
  servoShell: operatePort;
  recoder: dataRecoder;
  test: testRunner;
  constructor(
    servoShell: operatePort,
    dutShell: operatePort,
    enabledRecordingButton: (flag: boolean) => void,
    setSerialOutput: (s: string) => void
  ) {
    this.servoShell = servoShell;
    this.recoder = new dataRecoder(
      servoShell,
      enabledRecordingButton,
      setSerialOutput
    );
    this.recoder.setupDisconnectEvent();
    this.test = new testRunner(dutShell);
  }
  startMeasurement() {
    this.recoder.start();
  }
  stopMeasurement() {
    this.recoder.stop();
  }
  startDutConsole(addMessageToConsole: (s: string) => void) {
    this.test.selectPort(addMessageToConsole);
  }
  executeCommand(s: string) {
    this.test.sendCommand(s);
  }
  executeScript() {
    this.test.executeScript(this.scripts);
  }
  analyzePowerData() {
    this.recoder.analyzePowerData();
  }
  loadPowerData(s: string) {
    this.recoder.readJsonFile(s);
  }
  exportPowerData() {
    return this.recoder.writeJsonFile();
  }
}
