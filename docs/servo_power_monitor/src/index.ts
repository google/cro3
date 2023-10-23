// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {
  analyzePowerData,
  closeUSBPort,
  handleFileSelect,
  openUSBPort,
  savePowerDataToJSON,
  writeUSBPort,
  handleDragOver,
  kickWriteLoop,
  readLoop,
  stopMeasurementFlag,
  startMeasurementFlag,
  readUSBPort,
  readDUTSerialPort,
  readServoSerialPort,
  closeDUTSerialPort,
  closeServoSerialPort,
  openDUTSerialPort,
  writeDUTSerialPort,
  openServoSerialPort,
  writeServoSerialPort,
  executeScript,
} from './main';
import {
  addEmptyListItemToMessages,
  addMessageToConsole,
  analyzeAddClickEvent,
  closePopup,
  downloadAddClickEvent,
  dropZoneAddDragoverEvent,
  dropZoneAddDropEvent,
  executeScriptAddClickEvent,
  formAddSubmitEvent,
  haltAddClickEvent,
  readInputValue,
  requestSerialAddClickEvent,
  requestUSBAddClickEvent,
  selectDUTSerialAddClickEvent,
  setDownloadAnchor,
  setPopupCloseButton,
  useIsMeasuring,
} from './ui';

setPopupCloseButton();

let isDUTOpened = false;

selectDUTSerialAddClickEvent(async () => {
  await openDUTSerialPort();
  isDUTOpened = true;
  addEmptyListItemToMessages();
  addMessageToConsole('DUTPort is selected');
  addEmptyListItemToMessages();
  for (;;) {
    const chunk = await readDUTSerialPort();
    const chunk_split_list = chunk.split('\n');

    for (let i = 0; i < chunk_split_list.length - 1; i++) {
      addMessageToConsole(chunk_split_list[i]);
      addEmptyListItemToMessages();
    }
    addMessageToConsole(chunk_split_list[chunk_split_list.length - 1]);
  }
});

formAddSubmitEvent(async e => {
  e.preventDefault();
  if (!isDUTOpened) {
    closePopup();
  } else {
    await writeDUTSerialPort(readInputValue() + '\n');
  }
});

executeScriptAddClickEvent(async () => {
  if (!isDUTOpened) {
    closePopup();
  } else {
    executeScript();
  }
});

let isMeasuring = false;
let isSerial = false;

requestUSBAddClickEvent(async () => {
  startMeasurementFlag();
  await openUSBPort();
  isMeasuring = true;
  isSerial = false;
  useIsMeasuring(isMeasuring);
  try {
    kickWriteLoop(async s => writeUSBPort(s));
    readLoop(async () => readUSBPort());
  } catch (err) {
    console.error(`Disconnected: ${err}`);
    isMeasuring = false;
    useIsMeasuring(isMeasuring);
  }
});

requestSerialAddClickEvent(async () => {
  startMeasurementFlag();
  await openServoSerialPort();
  isMeasuring = true;
  isSerial = true;
  useIsMeasuring(isMeasuring);
  await writeServoSerialPort('help\n');
  // TODO: Implement something to check the validity of servo serial port

  kickWriteLoop(async s => writeServoSerialPort(s));
  readLoop(async () => readServoSerialPort());
});

// `disconnect` event is fired when a USB device is disconnected.
// c.f. https://wicg.github.io/webusb/#disconnect (5.1. Events)
navigator.usb.addEventListener('disconnect', () => {
  if (isMeasuring && !isSerial) {
    //  No need to call close() for the USB servoPort here because the
    //  specification says that
    // the servoPort will be closed automatically when a device is disconnected.
    isMeasuring = false;
    useIsMeasuring(isMeasuring);
    stopMeasurementFlag();
  }
});

// event when you disconnect serial port
navigator.serial.addEventListener('disconnect', async () => {
  if (isMeasuring && isSerial) {
    await closeServoSerialPort();
    isMeasuring = false;
    useIsMeasuring(isMeasuring);
    stopMeasurementFlag();
  }
  if (isDUTOpened) {
    await closeDUTSerialPort();
    isDUTOpened = false;
  }
});

downloadAddClickEvent(async () => {
  const dataStr = savePowerDataToJSON();
  setDownloadAnchor(dataStr);
});

haltAddClickEvent(async () => {
  stopMeasurementFlag();
  if (isSerial) {
    await closeServoSerialPort();
  } else {
    await closeUSBPort();
  }
  isMeasuring = false;
  useIsMeasuring(isMeasuring);
});

analyzeAddClickEvent(analyzePowerData);

dropZoneAddDragoverEvent(handleDragOver);
dropZoneAddDropEvent(handleFileSelect);
