// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import * as d3 from 'd3';
import Dygraph from 'dygraphs';
import moment from 'moment';

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

const encoder = new TextEncoder();
const decoder = new TextDecoder();

let DUTPort: SerialPort;
selectDUTSerialButton.addEventListener('click', async () => {
  DUTPort = await navigator.serial
    .requestPort({filters: [{usbVendorId: 0x18d1, usbProductId: 0x504a}]})
    .catch(e => {
      console.error(e);
      throw e;
    });
  await DUTPort.open({baudRate: 115200});
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
const input = document.getElementById('input') as HTMLInputElement;
form.addEventListener('submit', async e => {
  e.preventDefault();

  if (DUTPort === undefined) {
    overlay.classList.remove('closed');
    return;
  }
  const DUTWritable = DUTPort.writable;
  if (DUTWritable === null) return;
  const DUTWriter = DUTWritable.getWriter();
  await DUTWriter.write(encoder.encode(input.value + '\n'));
  input.value = '';
  await DUTWriter.releaseLock();
});

input.addEventListener('keydown', async e => {
  if (DUTPort === undefined) {
    overlay.classList.remove('closed');
  }
  const DUTWritable = DUTPort.writable;
  if (DUTWritable === null) return;
  const DUTWriter = DUTWritable.getWriter();
  if (e.ctrlKey && e.key === 'c') {
    await DUTWriter.write(encoder.encode('\x03\n'));
  }
  await DUTWriter.releaseLock();
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
    const DUTWritable = DUTPort.writable;
    if (DUTWritable === null) return;
    const DUTWriter = DUTWritable.getWriter();
    await DUTWriter.write(encoder.encode('cat > ./example.sh << EOF\n'));
    await DUTWriter.write(encoder.encode(scripts));
    await DUTWriter.write(encoder.encode('EOF\n'));
    await DUTWriter.write(encoder.encode('bash ./example.sh\n'));
    DUTWriter.releaseLock();
  }
});

const powerData: Array<Array<Date | number>> = [];
const g = new Dygraph('graph', powerData, {});
const utf8decoder = new TextDecoder('utf-8');
let output = '';
let halt = false;

let currentData: Array<Array<Date | number>>;
function updateGraph(data: Array<Array<Date | number>>) {
  if (data !== undefined && data.length > 0) {
    const toolTip = document.querySelector('#tooltip');
    if (toolTip !== null) {
      toolTip.classList.add('hidden');
    }
  }
  currentData = data;
  g.updateOptions(
    {
      file: data,
      labels: ['t', 'ina0'],
      showRoller: true,
      ylabel: 'Power (mW)',
      legend: 'always',
      showRangeSelector: true,
      connectSeparatedPoints: true,
      underlayCallback: function (canvas, area, g) {
        canvas.fillStyle = 'rgba(255, 255, 102, 1.0)';

        function highlight_period(x_start: number, x_end: number) {
          const canvas_left_x = g.toDomXCoord(x_start);
          const canvas_right_x = g.toDomXCoord(x_end);
          const canvas_width = canvas_right_x - canvas_left_x;
          canvas.fillRect(canvas_left_x, area.y, canvas_width, area.h);
        }
        highlight_period(10, 10);
      },
    },
    false
  );
}

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
    updateGraph(powerData);
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
function closeUSBPort() {
  try {
    device.close();
  } catch (e) {
    console.error(e);
  }
  requestUSBButton.disabled = false;
}

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
    try {
      device = await navigator.usb.requestDevice({
        filters: [
          {
            vendorId: 0x18d1 /* Google */,
            productId: 0x520d /* Servo v4p1 */,
          },
        ],
      });
    } catch (err) {
      console.error(`Error: ${err}`);
    }
    if (!device) {
      // device = null;
      return;
    }

    try {
      await device.open();
      requestUSBButton.disabled = true;
      await device.selectConfiguration(1);
      await device.claimInterface(usb_interface);
      kickWriteLoop(async s => {
        const data = new TextEncoder().encode(s);
        await device.transferOut(ep, data);
      });
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

  servoPort = await navigator.serial
    .requestPort({filters: [{usbVendorId: 0x18d1, usbProductId: 0x520d}]})
    .catch(e => {
      console.error(e);
      throw e;
    });
  await servoPort.open({baudRate: 115200});
  requestSerialButton.disabled = true;
  const servoWritable = servoPort.writable;
  if (servoWritable === null) return;
  const servoWriter = servoWritable.getWriter();
  await servoWriter.write(encoder.encode('help\n'));
  servoWriter.releaseLock();

  kickWriteLoop(async s => {
    const data = new TextEncoder().encode(s);
    const servoWritable = servoPort.writable;
    if (servoWritable === null) return;
    const servoWriter = servoWritable.getWriter();
    await servoWriter.write(data);
    servoWriter.releaseLock();
  });
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
    closeUSBPort();
  }
  if (requestSerialButton.disabled) {
    closeSerialPort();
  }
});

const ranges: Array<Array<number>> = [];
function paintHistogram(t0: number, t1: number) {
  // constants
  const xtick = 40;
  const boxWidth = 10;

  // setup a graph (drop if exists)
  const margin = {top: 60, right: 200, bottom: 0, left: 200};
  const area = d3.select('#d3area');
  const targetWidth =
    (area.node() as HTMLElement).getBoundingClientRect().width * 0.98;
  const targetHeight = 10000; // (area.node() as HTMLElement).getBoundingClientRect().height;
  const width = targetWidth - margin.left - margin.right;
  const svg = area
    .html('')
    .append('svg')
    .attr('height', targetHeight)
    .attr('width', targetWidth)
    .append('g')
    .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

  // y axis and its label
  const dataAll: Array<number> = currentData.map(
    (e: Array<Date | number>) => e[1] as number
  );
  const dataMin = d3.min(dataAll);
  const dataMax = d3.max(dataAll);
  if (dataMin === undefined || dataMax === undefined) return;
  const ymin = dataMin - 1000;
  const ymax = dataMax + 1000;
  const y = d3.scaleLinear().domain([ymin, ymax]).range([0, width]);
  svg.append('g').call(d3.axisTop(y));
  svg
    .append('text')
    .attr('text-anchor', 'end')
    .attr('x', width)
    .attr('y', -margin.top / 2)
    .attr('stroke', '#fff')
    .text('Power (mW)');

  ranges.push([t0, t1]);

  for (let i = 0; i < ranges.length; i++) {
    // compute data and place of i-th series
    const left = ranges[i][0];
    const right = ranges[i][1];
    const points = currentData.filter(
      (e: Array<Date | number>) =>
        typeof e[0] !== 'number' &&
        left <= e[0].getTime() &&
        e[0].getTime() <= right
    );

    const data: Array<number> = points.map(
      (e: Array<Date | number>) => e[1] as number
    );
    const center = xtick * (i + 1);

    // Compute statistics
    const data_sorted = data.sort(d3.ascending);
    const q1 = d3.quantile(data_sorted, 0.25);
    const median = d3.quantile(data_sorted, 0.5);
    const q3 = d3.quantile(data_sorted, 0.75);
    if (q1 === undefined || q3 === undefined) return;
    if (median === undefined) return;
    const interQuantileRange = q3 - q1;
    const lowerFence = q1 - 1.5 * interQuantileRange;
    const upperFence = q3 + 1.5 * interQuantileRange;
    const minValue = d3.min(data);
    const maxValue = d3.max(data);
    const mean = d3.mean(data);
    if (minValue === undefined || maxValue === undefined || mean === undefined)
      return;

    // min, mean, max
    svg
      .append('line')
      .attr('y1', center)
      .attr('y2', center)
      .attr('x1', y(minValue))
      .attr('x2', y(maxValue))
      .style('stroke-dasharray', '3, 3')
      .attr('stroke', '#aaa');
    svg
      .selectAll('toto')
      .data([minValue, mean, maxValue])
      .enter()
      .append('line')
      .attr('y1', center - boxWidth)
      .attr('y2', center + boxWidth)
      .attr('x1', d => {
        return y(d);
      })
      .attr('x2', d => {
        return y(d);
      })
      .style('stroke-dasharray', '3, 3')
      .attr('stroke', '#aaa');

    // box and line
    svg
      .append('line')
      .attr('y1', center)
      .attr('y2', center)
      .attr('x1', y(lowerFence))
      .attr('x2', y(upperFence))
      .attr('stroke', '#fff');
    svg
      .append('rect')
      .attr('y', center - boxWidth / 2)
      .attr('x', y(q1))
      .attr('width', y(q3) - y(q1))
      .attr('height', boxWidth)
      .attr('stroke', '#fff')
      .style('fill', '#69b3a2');
    svg
      .selectAll('toto')
      .data([lowerFence, median, upperFence])
      .enter()
      .append('line')
      .attr('y1', center - boxWidth / 2)
      .attr('y2', center + boxWidth / 2)
      .attr('x1', d => {
        return y(d);
      })
      .attr('x2', d => {
        return y(d);
      })
      .attr('stroke', '#fff');

    svg
      .append('text')
      .attr('text-anchor', 'end')
      .attr('alignment-baseline', 'baseline')
      .attr('y', center - boxWidth / 4)
      .attr('x', 0)
      .attr('font-size', boxWidth)
      .attr('stroke', '#fff')
      .text(`${moment(left).format()}`);
    svg
      .append('text')
      .attr('text-anchor', 'end')
      .attr('alignment-baseline', 'hanging')
      .attr('y', center + boxWidth / 4)
      .attr('x', 0)
      .attr('font-size', boxWidth)
      .attr('stroke', '#fff')
      .text(`${moment(right).format()}`);

    svg
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('alignment-baseline', 'baseline')
      .attr('y', center - boxWidth)
      .attr('x', y(mean))
      .attr('font-size', boxWidth)
      .attr('stroke', '#fff')
      .text(`mean:${mean | 0}`);

    svg
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('alignment-baseline', 'hanging')
      .attr('y', center + boxWidth)
      .attr('x', y(median))
      .attr('font-size', boxWidth)
      .attr('stroke', '#fff')
      .text(`median:${median}`);

    svg
      .append('text')
      .attr('text-anchor', 'start')
      .attr('alignment-baseline', 'hanging')
      .attr('y', center + boxWidth)
      .attr('x', y(ymax))
      .attr('font-size', boxWidth)
      .attr('stroke', '#fff')
      .text(`N:${data.length}`);
  }
}

function setupAnalyze() {
  const button = document.createElement('button');
  button.innerText = 'Analyze displayed range';
  controlDiv.appendChild(button);
  button.addEventListener('click', () => {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = g.xAxisRange();
    console.log(g.xAxisExtremes());
    const left = xrange[0];
    const right = xrange[1];
    paintHistogram(left, right);
  });
}
setupAnalyze();

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
      updateGraph(powerData);
    });
    r.readAsText(file);
  };

  const handleDragOver = (evt: DragEvent) => {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
  };
  const dropZone = document.getElementById('dropZone');
  if (dropZone === null) return;
  dropZone.innerText = 'Drop .json here';
  dropZone.addEventListener('dragover', handleDragOver, false);
  dropZone.addEventListener('drop', handleFileSelect, false);
}
setupDataLoad();
