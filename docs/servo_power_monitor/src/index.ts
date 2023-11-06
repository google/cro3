// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {OperatePort} from './operatePort';
import {PowerTestController} from './powerTestController';
import moment from 'moment';
import {testRunner} from './testRunner';
import {ServoController} from './servoController';

window.addEventListener('DOMContentLoaded', () => {
  const requestUsbButton = document.getElementById(
    'request-device'
  ) as HTMLButtonElement;
  const requestSerialButton = document.getElementById(
    'requestSerialButton'
  ) as HTMLButtonElement;
  const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
  const downloadButton = document.getElementById(
    'downloadButton'
  ) as HTMLButtonElement;
  const analyzeButton = document.getElementById(
    'analyzeButton'
  ) as HTMLButtonElement;
  const selectDutSerialButton = document.getElementById(
    'selectDutSerialButton'
  ) as HTMLButtonElement;
  const dutCommandForm = document.getElementById(
    'dutCommandForm'
  ) as HTMLFormElement;
  const dutCommandInput = document.getElementById(
    'dutCommandInput'
  ) as HTMLInputElement;
  const popupCloseButton = document.getElementById(
    'popup-close'
  ) as HTMLButtonElement;
  const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
  const messages = document.getElementById('messages') as HTMLDivElement;
  const executeScriptButton = document.getElementById(
    'executeScriptButton'
  ) as HTMLButtonElement;
  const dropZone = document.getElementById('dropZone') as HTMLSpanElement;
  const serial_output = document.getElementById(
    'serial_output'
  ) as HTMLDivElement;

  const servoController = new ServoController();
  const testController = new PowerTestController(
    servoController,
    enabledRecordingButton,
    setSerialOutput
  );
  const dutShell = new OperatePort(0x18d1, 0x504a);
  const runner = new testRunner(dutShell);
  testController.setupDisconnectEvent();
  runner.setupDisconnectEvent();

  requestSerialButton.addEventListener('click', () => {
    testController.startMeasurement(true);
  });
  requestUsbButton.addEventListener('click', () => {
    testController.startMeasurement(false);
  });
  haltButton.addEventListener('click', () => {
    testController.stopMeasurement();
  });
  selectDutSerialButton.addEventListener('click', () => {
    runner.selectPort(addMessageToConsole);
  });
  dutCommandForm.addEventListener('submit', e => formSubmit(e));
  dutCommandInput.addEventListener('keydown', e => sendCancel(e));
  analyzeButton.addEventListener('click', () => {
    testController.analyzePowerData();
  });
  executeScriptButton.addEventListener('click', () => executeScript());
  dropZone.addEventListener('dragover', e => handleDragOver(e), false);
  dropZone.addEventListener('drop', e => handleFileSelect(e), false);
  downloadButton.addEventListener('click', () => {
    const dataStr = testController.exportPowerData();
    setDownloadAnchor(dataStr);
  });
  popupCloseButton.addEventListener('click', () => {
    overlay.classList.add('closed');
  });

  function enabledRecordingButton(halt: boolean) {
    requestUsbButton.disabled = !halt;
    requestSerialButton.disabled = !halt;
    haltButton.disabled = halt;
    downloadButton.disabled = !halt;
    analyzeButton.disabled = !halt;
  }
  function setSerialOutput(s: string) {
    serial_output.textContent = s;
  }
  function readInputValue() {
    const res = dutCommandInput.value;
    dutCommandInput.value = '';
    return res;
  }
  function executeScript() {
    if (!runner.isOpened) {
      overlay.classList.remove('closed');
      return;
    }
    runner.executeScript();
  }
  async function formSubmit(e: Event) {
    e.preventDefault();
    if (!runner.isOpened) {
      overlay.classList.remove('closed');
      return;
    }
    await runner.executeCommand(readInputValue() + '\n');
  }
  // send cancel command to serial port when ctrl+C is pressed in input area
  async function sendCancel(e: KeyboardEvent) {
    if (!runner.isOpened) {
      overlay.classList.remove('closed');
      return;
    }
    if (e.ctrlKey && e.key === 'c') {
      await runner.sendCancel();
    }
  }
  function addMessageToConsole(s: string) {
    messages.textContent += s;
    messages.scrollTo(0, messages.scrollHeight);
  }
  function handleDragOver(evt: DragEvent) {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
  }
  function handleFileSelect(evt: DragEvent) {
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
      testController.loadPowerData(r.result as string);
    });
    r.readAsText(file);
  }
  function setDownloadAnchor(dataStr: string) {
    const dlAnchorElem = document.getElementById('downloadAnchorElem');
    if (dlAnchorElem === null) return;
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
    dlAnchorElem.click();
  }
});
