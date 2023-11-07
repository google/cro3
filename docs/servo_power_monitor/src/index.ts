// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal
import moment from 'moment';
import {OperatePort} from './operatePort';
import {PowerTestController} from './powerTestController';
import {testRunner} from './testRunner';
import {ServoController} from './servoController';
import {Ui} from './ui';

window.addEventListener('DOMContentLoaded', () => {
  const ui = new Ui();
  const servoController = new ServoController();
  const testController = new PowerTestController(ui, servoController);
  const dutShell = new OperatePort(0x18d1, 0x504a);
  const runner = new testRunner(ui, dutShell);
  testController.setupDisconnectEvent();
  runner.setupDisconnectEvent();

  ui.requestSerialButton.addEventListener('click', () => {
    testController.startMeasurement(true);
  });
  ui.requestUsbButton.addEventListener('click', () => {
    testController.startMeasurement(false);
  });
  ui.haltButton.addEventListener('click', () => {
    testController.stopMeasurement();
  });
  ui.selectDutSerialButton.addEventListener('click', () => {
    runner.selectPort();
  });
  ui.dutCommandForm.addEventListener('submit', async e => {
    e.preventDefault();
    if (!runner.isOpened) {
      ui.overlay.classList.remove('closed');
      return;
    }
    await runner.executeCommand(ui.readInputValue() + '\n');
  });
  // send cancel command to serial port when ctrl+C is pressed in input area
  ui.dutCommandInput.addEventListener('keydown', async e => {
    if (!runner.isOpened) {
      ui.overlay.classList.remove('closed');
      return;
    }
    if (e.ctrlKey && e.key === 'c') {
      await runner.sendCancel();
    }
  });
  ui.analyzeButton.addEventListener('click', () => {
    testController.analyzePowerData();
  });
  ui.executeScriptButton.addEventListener('click', () => {
    if (!runner.isOpened) {
      ui.overlay.classList.remove('closed');
      return;
    }
    runner.executeScript();
  });
  ui.dropZone.addEventListener(
    'dragover',
    e => {
      e.stopPropagation();
      e.preventDefault();
      const eventDataTransfer = e.dataTransfer;
      if (eventDataTransfer === null) return;
      eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
    },
    false
  );
  ui.dropZone.addEventListener(
    'drop',
    e => {
      e.stopPropagation();
      e.preventDefault();
      const eventDataTransfer = e.dataTransfer;
      if (eventDataTransfer === null) return;
      const file = eventDataTransfer.files[0];
      if (file === undefined) return;
      const r = new FileReader();
      r.addEventListener('load', () => {
        testController.loadPowerData(r.result as string);
      });
      r.readAsText(file);
    },
    false
  );
  ui.downloadButton.addEventListener('click', () => {
    const dataStr = testController.exportPowerData();
    ui.dlAnchorElem.setAttribute('href', dataStr);
    ui.dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
    ui.dlAnchorElem.click();
  });
  ui.popupCloseButton.addEventListener('click', () => {
    ui.overlay.classList.add('closed');
  });
});
