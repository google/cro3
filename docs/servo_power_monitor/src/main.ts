import * as d3 from 'd3';
import Dygraph from 'dygraphs';
import moment from 'moment';
import {
  addMessageToConsole,
  closePopup,
  enabledRecordingButton,
  readInputValue,
  setDownloadAnchor,
} from './ui';

const INTERVAL_MS = 100;
const CANCEL_CMD = '\x03\n';
const encoder = new TextEncoder();
const utf8decoder = new TextDecoder('utf-8');
let halt = false;
let inProgress = false;

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
      await new Promise(r => setTimeout(r, INTERVAL_MS));
    }
  };
  setTimeout(f, INTERVAL_MS);
}

let servoPort: SerialPort, servoReader: ReadableStreamDefaultReader;
let DutPort: SerialPort, DutReader: ReadableStreamDefaultReader;

async function openServoSerialPort() {
  servoPort = await navigator.serial
    .requestPort({
      filters: [{usbVendorId: 0x18d1, usbProductId: 0x520d}],
    })
    .catch(e => {
      console.error(e);
      throw e;
    });
  await servoPort.open({baudRate: 115200});
}

async function closeServoSerialPort() {
  await servoReader.cancel();
  await servoReader.releaseLock();
  try {
    await servoPort.close();
  } catch (e) {
    console.error(e);
    throw e;
  }
}

async function readServoSerialPort() {
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
}

async function writeServoSerialPort(s: string) {
  const writable = servoPort.writable;
  if (writable === null) return;
  const writer = writable.getWriter();
  await writer.write(encoder.encode(s));
  writer.releaseLock();
}

async function openDutSerialPort() {
  DutPort = await navigator.serial
    .requestPort({
      filters: [{usbVendorId: 0x18d1, usbProductId: 0x504a}],
    })
    .catch(e => {
      console.error(e);
      throw e;
    });
  await DutPort.open({baudRate: 115200});
}

async function closeDutSerialPort() {
  await DutReader.cancel();
  await DutReader.releaseLock();
  try {
    await DutPort.close();
  } catch (e) {
    console.error(e);
    throw e;
  }
}

async function readDutSerialPort() {
  const DutReadable = DutPort.readable;
  if (DutReadable === null) return '';
  DutReader = DutReadable.getReader();
  try {
    for (;;) {
      const {value, done} = await DutReader.read();
      if (done) {
        // |DutReader| has been canceled.
        DutReader.releaseLock();
        return '';
      }
      return utf8decoder.decode(value, {stream: true});
    }
  } catch (error) {
    DutReader.releaseLock();
    console.error(error);
    throw error;
  } finally {
    DutReader.releaseLock();
  }
}

async function writeDutSerialPort(s: string) {
  const writable = DutPort.writable;
  if (writable === null) return;
  const writer = writable.getWriter();
  await writer.write(encoder.encode(s));
  writer.releaseLock();
}

let currentData: Array<Array<Date | number>>;
function updateGraph(g: Dygraph, data: Array<Array<Date | number>>) {
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

const powerData: Array<Array<Date | number>> = [];
const g = new Dygraph('graph', powerData, {});
let output = '';

const serial_output = document.getElementById(
  'serial_output'
) as HTMLDivElement;

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

export function analyzePowerData() {
  // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
  const xrange = g.xAxisRange();
  console.log(g.xAxisExtremes());
  const left = xrange[0];
  const right = xrange[1];
  paintHistogram(left, right);
}

export function handleFileSelect(evt: DragEvent) {
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
}

export function handleDragOver(evt: DragEvent) {
  evt.stopPropagation();
  evt.preventDefault();
  const eventDataTransfer = evt.dataTransfer;
  if (eventDataTransfer === null) return;
  eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
}

let isDutOpened = false;
export async function selectDutSerial() {
  await openDutSerialPort();
  isDutOpened = true;
  addMessageToConsole('DutPort is selected');
  for (;;) {
    const chunk = await readDutSerialPort();
    addMessageToConsole(chunk);
  }
}

export async function formSubmit(e: Event) {
  e.preventDefault();
  if (!isDutOpened) {
    closePopup();
    return;
  }
  await writeDutSerialPort(readInputValue() + '\n');
}

// send cancel command to serial port when ctrl+C is pressed in input area
export async function cancelSubmit(e: KeyboardEvent) {
  if (!isDutOpened) {
    closePopup();
    return;
  }
  if (e.ctrlKey && e.key === 'c') {
    await writeDutSerialPort(CANCEL_CMD);
  }
}

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

export async function executeScript() {
  if (!isDutOpened) {
    closePopup();
  } else {
    await writeDutSerialPort('cat > ./example.sh << EOF\n');
    await writeDutSerialPort(scripts);
    await writeDutSerialPort('EOF\n');
    await writeDutSerialPort('bash ./example.sh\n');
  }
}

let isSerial = false;

export async function requestSerial() {
  halt = false;
  await openServoSerialPort();
  isSerial = true;
  enabledRecordingButton(halt);
  await writeServoSerialPort('help\n');
  // TODO: Implement something to check the validity of servo serial port

  kickWriteLoop(async s => writeServoSerialPort(s));
  readLoop(async () => readServoSerialPort());
}

export async function disconnectUsbPort() {
  if (!halt && !isSerial) {
    //  No need to call close() for the Usb servoPort here because the
    //  specification says that
    // the servoPort will be closed automatically when a device is disconnected.
    halt = true;
    inProgress = false;
    enabledRecordingButton(halt);
  }
}

export async function disconnectSerialPort() {
  if (!halt && isSerial) {
    await closeServoSerialPort();
    halt = true;
    inProgress = false;
    enabledRecordingButton(halt);
  }
  if (isDutOpened) {
    await closeDutSerialPort();
    isDutOpened = false;
  }
}

export function downloadJSONFile() {
  const dataStr =
    'data:text/json;charset=utf-8,' +
    encodeURIComponent(JSON.stringify({power: powerData}));
  setDownloadAnchor(dataStr);
}

export async function stopMeasurement() {
  halt = true;
  inProgress = false;
  await closeServoSerialPort();
  enabledRecordingButton(halt);
}
