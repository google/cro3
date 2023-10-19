// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import * as d3 from 'd3';
import Dygraph from 'dygraphs';
import moment from 'moment';
import {
  closeUSBPort,
  openSerialPort,
  openUSBPort,
  paintHistogram,
  updateGraph,
  writeSerialPort,
  writeUSBPort,
} from './main';
import {handleDragOver} from './ui';

const intervalMs = 100;

const downloadButton = document.getElementById(
  'downloadButton'
) as HTMLButtonElement;
const requestUSBButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const serial_output = document.getElementById(
  'serial_output'
) as HTMLDivElement;
const controlDiv = document.getElementById('controlDiv') as HTMLDivElement;
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

const powerData: Array<Array<Date | number>> = [];
const g = new Dygraph('graph', powerData, {});
const utf8decoder = new TextDecoder('utf-8');
let output = '';
let halt = false;

let inProgress = false;
function pushOutput(s: string) {
  output += s;

  const splitted = output.split('\n').filter(s => s.trim().length > 10);
  if (
    splitted.length > 0 &&
    splitted[splitted.length - 1].indexOf('Alert limit') >= 0
  ) {
    const powerString = splitted.find(s => s.startsWith('Power'));
    if (powerString === undefined) return;
    const power = parseInt(powerString.split('=>')[1].trim().split(' ')[0]);
    const e: Array<Date | number> = [new Date(), power];
    powerData.push(e);
    updateGraph(g, powerData);
    serial_output.innerText = output;
    output = '';
    inProgress = false;
  }
}

function kickWriteLoop(writeFn: (s: string) => Promise<void>) {
  const f = async () => {
    while (!halt) {
      if (inProgress) {
        console.error('previous request is in progress! skip...');
      } else {
        inProgress = true;
      }

      // ina 0 and 1 seems to be the same
      // ina 2 is something but not useful
      const cmd = 'ina 0\n';
      await writeFn(cmd);
      await new Promise(r => setTimeout(r, intervalMs));
    }
  };
  setTimeout(f, intervalMs);
}
async function readLoop(readFn: () => Promise<string>) {
  while (!halt) {
    try {
      const s = await readFn();
      if (s === '' || !s.length) {
        continue;
      }
      pushOutput(s);
    } catch (e) {
      // break the loop here because `disconnect` event is not called in Chrome
      // for some reason when the loop continues. And no need to throw error
      // here because it is thrown in readFn.
      break;
    }
  }
}

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
    halt = false;
    device = await openUSBPort();
    requestUSBButton.disabled = true;

    try {
      kickWriteLoop(async s => writeUSBPort(device, s));
      readLoop(async () => {
        try {
          const result = await device.transferIn(ep, 64);
          if (result.status === 'stall') {
            await device.clearHalt('in', ep);
            throw result;
          }
          const resultData = result.data;
          if (resultData === undefined) return '';
          const result_array = new Int8Array(resultData.buffer);
          return utf8decoder.decode(result_array);
        } catch (e) {
          // If halt is true, it's when the stop button is pressed. Therefore,
          // we can ignore the error.
          if (!halt) {
            console.error(e);
            throw e;
          }
          return '';
        }
      });
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
  halt = false;

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
    halt = true;
    requestUSBButton.disabled = false;
    inProgress = false;
  }
});

// event when you disconnect serial servoPort
navigator.serial.addEventListener('disconnect', () => {
  if (requestSerialButton.disabled) {
    halt = true;
    inProgress = false;
    closeSerialPort();
  }
});

downloadButton.addEventListener('click', async () => {
  const dataStr =
    'data:text/json;charset=utf-8,' +
    encodeURIComponent(JSON.stringify({power: powerData}));
  const dlAnchorElem = document.getElementById('downloadAnchorElem');
  if (dlAnchorElem === null) return;
  dlAnchorElem.setAttribute('href', dataStr);
  dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
  dlAnchorElem.click();
});

const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
haltButton.addEventListener('click', () => {
  halt = true;
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
analyzeButton.addEventListener('click', () => {
  // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
  const xrange = g.xAxisRange();
  console.log(g.xAxisExtremes());
  const left = xrange[0];
  const right = xrange[1];
  paintHistogram(left, right);
});

function setupDataLoad() {
  const handleFileSelect = (evt: DragEvent) => {
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
      const powerData = data.power.map((d: string) => [new Date(d[0]), d[1]]);
      updateGraph(g, powerData);
    });
    r.readAsText(file);
  };

  const dropZone = document.getElementById('dropZone');
  if (dropZone === null) return;
  dropZone.innerText = 'Drop .json here';
  dropZone.addEventListener('dragover', handleDragOver, false);
  dropZone.addEventListener('drop', handleFileSelect, false);
}
setupDataLoad();
