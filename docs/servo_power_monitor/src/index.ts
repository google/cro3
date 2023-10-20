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
import {setDownloadAnchor} from './ui';

const downloadButton = document.getElementById(
  'downloadButton'
) as HTMLButtonElement;
const requestUSBButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const selectDUTSerialButton = document.getElementById(
  'selectDUTSerialButton'
) as HTMLButtonElement;
const executeScriptButton = document.getElementById(
  'executeScriptButton'
) as HTMLButtonElement;
const messages = document.getElementById('messages') as HTMLUListElement;
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;

popupCloseButton.addEventListener('click', () => {
  overlay.classList.add('closed');
});

const decoder = new TextDecoder();

let DUTPort: SerialPort;
selectDUTSerialButton.addEventListener('click', async () => {
  DUTPort = await openSerialPort(0x18d1, 0x504a);
  let listItem = document.createElement('li');
  listItem.textContent = 'DUTPort is selected';
  messages.appendChild(listItem);
  const DUTReadable = DUTPort.readable;
  if (DUTReadable === null) return;
  const DUTReader = DUTReadable.getReader();
  listItem = document.createElement('li');
  messages.appendChild(listItem);
  DUTReader.read().then(function processText({done, value}): void {
    if (done) {
      console.log('Stream complete');
      return;
    }

    const chunk = decoder.decode(value, {stream: true});
    const chunk_split_list = chunk.split('\n');

    for (let i = 0; i < chunk_split_list.length - 1; i++) {
      listItem.textContent += chunk_split_list[i];
      listItem = document.createElement('li');
      messages.appendChild(listItem);
    }
    listItem.textContent += chunk_split_list[chunk_split_list.length - 1];
    messages.scrollTo(0, messages.scrollHeight);

    DUTReader.read().then(processText);
  });
});

const form = document.getElementById('form') as HTMLFormElement;
form.addEventListener('submit', async e => {
  e.preventDefault();

  if (DUTPort === undefined) {
    overlay.classList.remove('closed');
  } else {
    const input = document.getElementById('input') as HTMLInputElement | null;
    if (input === null) return;
    await writeSerialPort(DUTPort, input.value + '\n');
    input.value = '';
  }
});

executeScriptButton.addEventListener('click', async () => {
  if (DUTPort === undefined) {
    overlay.classList.remove('closed');
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

const utf8decoder = new TextDecoder('utf-8');

let device: USBDevice;

let servoPort: SerialPort;
let servoReader: ReadableStreamDefaultReader;
function closeSerialPort() {
  servoReader.cancel();
  servoReader.releaseLock();
  try {
    servoPort.close();
  } catch (e) {
    console.error(e);
  }
  requestSerialButton.disabled = false;
}

function setupStartUSBButton() {
  const usb_interface = 0;
  const ep = usb_interface + 1;
  requestUSBButton.addEventListener('click', async () => {
    startMeasurementFlag();
    device = await openUSBPort();
    requestUSBButton.disabled = true;

    try {
      kickWriteLoop(async s => writeUSBPort(device, s));
      readLoop(async () => readUSBPort(device));
    } catch (err) {
      console.error(`Disconnected: ${err}`);
      requestUSBButton.disabled = false;
    }
  });
  window.addEventListener(
    'keydown',
    async event => {
      if (!device) {
        return;
      }
      let data;
      if (event.key.length === 1) {
        data = new Int8Array([event.key.charCodeAt(0)]);
      } else if (event.code === 'Enter') {
        data = new Uint8Array([0x0a]);
      } else {
        return;
      }
      await device.transferOut(ep, data);
    },
    true
  );
}
setupStartUSBButton();

requestSerialButton.addEventListener('click', async () => {
  startMeasurementFlag();

  servoPort = await openSerialPort(0x18d1, 0x520d);
  requestSerialButton.disabled = true;
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
  if (requestUSBButton.disabled) {
    //  No need to call close() for the USB servoPort here because the
    //  specification says that
    // the servoPort will be closed automatically when a device is disconnected.
    requestUSBButton.disabled = false;
    stopMeasurementFlag();
  }
});

// event when you disconnect serial port
navigator.serial.addEventListener('disconnect', async () => {
  if (requestSerialButton.disabled) {
    closeSerialPort();
    stopMeasurementFlag();
  }
});

downloadButton.addEventListener('click', async () => {
  const dataStr = savePowerDataToJSON();
  setDownloadAnchor(dataStr);
});

const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
haltButton.addEventListener('click', () => {
  stopMeasurementFlag();
  if (requestUSBButton.disabled) {
    closeUSBPort(device);
    requestUSBButton.disabled = false;
  }
  if (requestSerialButton.disabled) {
    closeSerialPort();
  }
});

const analyzeButton = document.getElementById(
  'analyzeButton'
) as HTMLButtonElement;
analyzeButton.addEventListener('click', analyzePowerData);

const dropZone = document.getElementById('dropZone') as HTMLSpanElement;
dropZone.addEventListener('dragover', handleDragOver, false);
dropZone.addEventListener('drop', handleFileSelect, false);
