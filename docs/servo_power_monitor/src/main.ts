import * as d3 from 'd3';
import Dygraph from 'dygraphs';
import moment from 'moment';

const encoder = new TextEncoder();
const utf8decoder = new TextDecoder('utf-8');

// let servoPort: SerialPort;
// let servoReader: ReadableStreamDefaultReader;

export async function openSerialPort(
  usbVendorId: number,
  usbProductId: number
) {
  const port = await navigator.serial
    .requestPort({
      filters: [{usbVendorId: usbVendorId, usbProductId: usbProductId}],
    })
    .catch(e => {
      console.error(e);
      throw e;
    });
  await port.open({baudRate: 115200});
  return port;
}

export async function writeSerialPort(port: SerialPort, s: string) {
  const writable = port.writable;
  if (writable === null) return;
  const writer = writable.getWriter();
  await writer.write(encoder.encode(s));
  writer.releaseLock();
}

// export async function openServoSerialPort() {
//   servoPort = await openSerialPort(0x18d1, 0x520d);
// }

// export function closeServoSerialPort() {
//   servoReader.cancel();
//   servoReader.releaseLock();
//   try {
//     servoPort.close();
//   } catch (e) {
//     console.error(e);
//   }
// }

// export async function writeServoSerialPort(s: string) {
//   const servoWritable = servoPort.writable;
//   if (servoWritable === null) return;
//   const servoWriter = servoWritable.getWriter();
//   await servoWriter.write(encoder.encode(s));
//   servoWriter.releaseLock();
// }

// export async function readServoSerialPort() {
//   const servoReadable = servoPort.readable;
//   if (servoReadable === null) return '';
//   servoReader = servoReadable.getReader();
//   try {
//     for (;;) {
//       const {value, done} = await servoReader.read();
//       if (done) {
//         // |servoReader| has been canceled.
//         servoReader.releaseLock();
//         return '';
//       }
//       return utf8decoder.decode(value);
//     }
//   } catch (error) {
//     servoReader.releaseLock();
//     console.error(error);
//     throw error;
//   } finally {
//     servoReader.releaseLock();
//   }
// }

// let device: USBDevice;
const usb_interface = 0;
const ep = usb_interface + 1;

export async function openUSBPort() {
  const device = await navigator.usb
    .requestDevice({filters: [{vendorId: 0x18d1, productId: 0x520d}]})
    .catch(e => {
      console.error(e);
      throw e;
    });
  await device.open();
  await device.selectConfiguration(1);
  await device.claimInterface(usb_interface);
  return device;
}

export function closeUSBPort(device: USBDevice) {
  try {
    device.close();
  } catch (e) {
    console.error(e);
  }
}

export async function writeUSBPort(device: USBDevice, s: string) {
  await device.transferOut(ep, encoder.encode(s));
}

// export async function readUSBPort() {
//   try {
//     const result = await device.transferIn(ep, 64);
//     if (result.status === 'stall') {
//       await device.clearHalt('in', ep);
//       throw result;
//     }
//     const resultData = result.data;
//     if (resultData === undefined) return '';
//     const result_array = new Int8Array(resultData.buffer);
//     return utf8decoder.decode(result_array);
//   } catch (e) {
//     // If halt is true, it's when the stop button is pressed. Therefore,
//     // we can ignore the error.
//     if (!halt) {
//       console.error(e);
//       throw e;
//     }
//     return '';
//   }
// }

// let DUTPort: SerialPort;

// export async function openDUTSerialPort() {
//   DUTPort = await openSerialPort(0x18d1, 0x504a);
// }

// export async function writeDUTPort(s: string) {
//   const DUTWritable = DUTPort.writable;
//   if (DUTWritable === null) return;
//   const DUTWriter = DUTWritable.getWriter();
//   await DUTWriter.write(encoder.encode(s));
//   await DUTWriter.releaseLock();
// }

// export async function readDUTSerialPort() {
//   const DUTReadable = DUTPort.readable;
//   if (DUTReadable === null) return;
//   const DUTReader = DUTReadable.getReader();
//   DUTReader.read().then(function processText({done, value}): void {
//     if (done) {
//       console.log('Stream complete');
//       return;
//     }

//     const chunk = decoder.decode(value, {stream: true});
//     const chunk_split_list = chunk.split('\n');

//     for (let i = 0; i < chunk_split_list.length - 1; i++) {
//       listItem.textContent += chunk_split_list[i];
//       listItem = document.createElement('li');
//       messages.appendChild(listItem);
//     }
//     listItem.textContent += chunk_split_list[chunk_split_list.length - 1];
//     messages.scrollTo(0, messages.scrollHeight);

//     DUTReader.read().then(processText);
//   });
// }

let currentData: Array<Array<Date | number>>;
export function updateGraph(g: Dygraph, data: Array<Array<Date | number>>) {
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

const ranges: Array<Array<number>> = [];
export function paintHistogram(t0: number, t1: number) {
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
