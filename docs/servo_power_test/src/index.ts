// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal
import moment from 'moment';
import {OperatePort} from './operate_port';
import {PowerTestController} from './power_test_controller';
import {TestRunner} from './test_runner';
import {ServoController} from './servo_controller';
import {Ui} from './ui';

window.addEventListener('DOMContentLoaded', () => {
  const ui = new Ui();
  const servoController = new ServoController();
  const dutShell = new OperatePort(0x18d1, 0x504a);
  const runner = new TestRunner(ui, dutShell);
  const testController = new PowerTestController(ui, servoController, runner);
  testController.setupDisconnectEvent();

  ui.requestSerialButton.addEventListener('click', () => {
    testController.startMeasurement();
  });
  ui.haltButton.addEventListener('click', () => {
    testController.stopMeasurement();
  });
  ui.itrSelector.addEventListener('change', () => {
    const selectedItr = ui.itrSelector.selectedIndex;
    testController.showSelectedItrGraph(selectedItr);
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
  ui.addConfigButton.addEventListener('click', () => {
    ui.addConfigInputArea();
  });
});
