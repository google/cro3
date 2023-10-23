// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {
  analyzePowerData,
  closeUSBPort,
  handleFileSelect,
  openSerialPort,
  openUSBPort,
  savePowerDataToJSON,
  writeSerialPort,
  writeUSBPort,
  handleDragOver,
  kickWriteLoop,
  readLoop,
  stopMeasurementFlag,
  startMeasurementFlag,
  readUSBPort,
} from './main';
import {
  addEmptyListItemToMessages,
  addMessageToConsole,
  closePopup,
  downloadButtonAddClickEvent,
  executeScriptAddClickEvent,
  requestSerialAddClickEvent,
  requestUSBAddClickEvent,
  selectDUTSerialAddClickEvent,
  setDownloadAnchor,
  setPopupCloseButton,
  useIsMeasuring,
} from './ui';

setPopupCloseButton();

const utf8decoder = new TextDecoder('utf-8');

let DUTPort: SerialPort;
selectDUTSerialAddClickEvent(async () => {
  DUTPort = await openSerialPort(0x18d1, 0x504a);
  addEmptyListItemToMessages();
  addMessageToConsole('DUTPort is selected');
  addEmptyListItemToMessages();
  for (;;) {
    const DUTReadable = DUTPort.readable;
    if (DUTReadable === null) return;
    const DUTReader = DUTReadable.getReader();
    try {
      for (;;) {
        const {value, done} = await DUTReader.read();
        if (done) {
          // |DUTReader| has been canceled.
          DUTReader.releaseLock();
          break;
        }
        const chunk = utf8decoder.decode(value, {stream: true});
        const chunk_split_list = chunk.split('\n');

        for (let i = 0; i < chunk_split_list.length - 1; i++) {
          addMessageToConsole(chunk_split_list[i]);
          addEmptyListItemToMessages();
        }
        addMessageToConsole(chunk_split_list[chunk_split_list.length - 1]);
      }
    } catch (error) {
      DUTReader.releaseLock();
      console.error(error);
      throw error;
    } finally {
      DUTReader.releaseLock();
    }
  }
});

const form = document.getElementById('form') as HTMLFormElement;
form.addEventListener('submit', async e => {
  e.preventDefault();

  if (DUTPort === undefined) {
    closePopup();
  } else {
    const input = document.getElementById('input') as HTMLInputElement;
    await writeSerialPort(DUTPort, input.value + '\n');
    input.value = '';
  }
});

executeScriptAddClickEvent(async () => {
  if (DUTPort === undefined) {
    closePopup();
  } else {
    // shell script
    const scripts = `#!/bin/bash -e
function workload () {
    ectool chargecontrol idle
    stress-ng -c 1 -t \\$1
    echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;

    writeSerialPort(DUTPort, 'cat > ./example.sh << EOF\n');
    writeSerialPort(DUTPort, scripts);
    writeSerialPort(DUTPort, 'EOF\n');
    writeSerialPort(DUTPort, 'bash ./example.sh\n');
  }
});

let servoPort: SerialPort;
let servoReader: ReadableStreamDefaultReader;

let isMeasuring = false;
let isSerial = false;

function closeSerialPort() {
  servoReader.cancel();
  servoReader.releaseLock();
  try {
    servoPort.close();
  } catch (e) {
    console.error(e);
  }
  isMeasuring = false;
  useIsMeasuring(isMeasuring);
}

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

  servoPort = await openSerialPort(0x18d1, 0x520d);
  isMeasuring = true;
  isSerial = true;
  useIsMeasuring(isMeasuring);
  writeSerialPort(servoPort, 'help\n');

  kickWriteLoop(async s => writeSerialPort(servoPort, s));
  readLoop(async () => {
    const servoReadable = servoPort.readable;
    if (servoReadable === null) return '';
    servoReader = servoReadable.getReader();
    try {
      for (;;) {
        const {value, done} = await servoReader.read();
        if (done) {
          // |servoReader| has been canceled.
          servoReader.releaseLock();
          return '';
        }
        return utf8decoder.decode(value);
      }
    } catch (error) {
      servoReader.releaseLock();
      console.error(error);
      throw error;
    } finally {
      servoReader.releaseLock();
    }
  });
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
    isMeasuring = false;
    useIsMeasuring(isMeasuring);
    closeSerialPort();
    stopMeasurementFlag();
  }
});

downloadButtonAddClickEvent(async () => {
  const dataStr = savePowerDataToJSON();
  setDownloadAnchor(dataStr);
});

const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
haltButton.addEventListener('click', () => {
  stopMeasurementFlag();
  if (isSerial) {
    closeSerialPort();
  } else {
    closeUSBPort();
  }
  isMeasuring = false;
  useIsMeasuring(isMeasuring);
});

const analyzeButton = document.getElementById(
  'analyzeButton'
) as HTMLButtonElement;
analyzeButton.addEventListener('click', analyzePowerData);

const dropZone = document.getElementById('dropZone') as HTMLSpanElement;
dropZone.addEventListener('dragover', handleDragOver, false);
dropZone.addEventListener('drop', handleFileSelect, false);
