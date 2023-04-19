// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import * as d3 from 'd3';
import Dygraph from 'dygraphs';
import moment from 'moment';

const intervalMs = 100;

const controlDiv = document.getElementById('controlDiv') as HTMLDivElement;
let powerData = [];
const g = new Dygraph('graph', powerData, {});
const utf8decoder = new TextDecoder('utf-8');
let output = '';
let halt = false;

let currentData = undefined;
function updateGraph(data) {
  currentData = data;
  g.updateOptions(
      {
        file: data,
        labels: ['t', 'ina0', 'ina1'],
        showRoller: true,
        // customBars: true,
        ylabel: 'Power (mW)',
        legend: 'always',
        showRangeSelector: true,
        connectSeparatedPoints: true,
        underlayCallback: function(canvas, area, g) {
          canvas.fillStyle = 'rgba(255, 255, 102, 1.0)';

          function highlight_period(x_start: number, x_end: number) {
            const canvas_left_x = g.toDomXCoord(x_start);
            const canvas_right_x = g.toDomXCoord(x_end);
            const canvas_width = canvas_right_x - canvas_left_x;
            canvas.fillRect(canvas_left_x, area.y, canvas_width, area.h);
          }
          highlight_period(10, 10);
        }
      },
      false);
}

let inaIndex = 0;
function pushOutput(s: string) {
  output += s

  let splitted = output.split('\n').filter((s) => s.trim().length > 10);
  if (splitted.length > 0 &&
      splitted[splitted.length - 1].indexOf('Alert limit') >= 0) {
    let power = parseInt(splitted.find((s) => s.startsWith('Power'))
                             .split('=>')[1]
                             .trim()
                             .split(' ')[0]);
    let e: Array<Date|Number> = [new Date(), null, null];
    e[(inaIndex&1)+1] = power;
    inaIndex += 1;
    powerData.push(e);
    updateGraph(powerData);
    serial_output.innerText = output;
    output = '';
  }
}

const requestSerialButton =
    document.getElementById('requestSerialButton') as HTMLButtonElement;
requestSerialButton.addEventListener('click', () => {
  halt = false;
  navigator.serial
      .requestPort({filters: [{usbVendorId: 0x18d1, usbProductId: 0x520d}]})
      .then(async (port) => {
        // Connect to `port` or add it to the list of available ports.
        await port.open({baudRate: 115200});
        const encoder = new TextEncoder();
        const writer = port.writable.getWriter();
        await writer.write(encoder.encode('help\n'));
        writer.releaseLock();

        // Launch write loop
        const f = async (_: any) => {
          while (!halt) {
            let data = new TextEncoder().encode('ina 0\n');
            const writer = port.writable.getWriter();
            await writer.write(data);
            writer.releaseLock();
            await new Promise(r => setTimeout(r, intervalMs));
          }
        };
        setTimeout(f, 1000);

        // read loop
        while (!halt) {
          while (port.readable) {
            const reader = port.readable.getReader();
            try {
              while (true) {
                const {value, done} = await reader.read();
                if (done) {
                  // |reader| has been canceled.
                  break;
                }
                pushOutput(utf8decoder.decode(value));
              }
            } catch (error) {
              console.log(error);
            } finally {
              reader.releaseLock();
            }
          }
        }
      })
      .catch((e) => {
        // The user didn't select a port.
        console.log(e);
      });
});

let downloadButton =
    document.getElementById('downloadButton') as HTMLButtonElement;
downloadButton.addEventListener('click', async () => {
  const dataStr = 'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: powerData}));
  const dlAnchorElem = document.getElementById('downloadAnchorElem');
  dlAnchorElem.setAttribute('href', dataStr);
  dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
  dlAnchorElem.click();
});

let button = document.getElementById('request-device') as HTMLButtonElement;
let serial_output = document.getElementById('serial_output') as HTMLDivElement;
let device: USBDevice;
let usb_interface = 0;
let ep = usb_interface + 1;
button.addEventListener('click', async () => {
  halt = false;
  device = null;
  button.disabled = true;
  try {
    device = await navigator.usb.requestDevice({
      filters: [{
        vendorId: 0x18d1,  /* Google */
        productId: 0x520d, /* Servo v4p1 */
      }]
    });
  } catch (err) {
    console.log(`Error: ${err}`);
  }
  if (!device) {
    device = null;
    button.disabled = false;
    return;
  }

  try {
    await device.open();
    await device.selectConfiguration(1);
    await device.claimInterface(usb_interface);

    const f = async (_event: any) => {
      while (!halt) {
        let data = new TextEncoder().encode('ina 0\n');
        await device.transferOut(ep, data);
        await new Promise(r => setTimeout(r, intervalMs));
      }
    };
    setTimeout(f, intervalMs);

    while (!halt) {
      let result = await device.transferIn(ep, 64);
      if (result.status === 'stall') {
        await device.clearHalt('in', ep);
        continue;
      }
      const result_array = new Int8Array(result.data.buffer);
      pushOutput(utf8decoder.decode(result_array));
    }
  } catch (err) {
    console.log(`Disconnected: ${err}`);
    device = null;
    button.disabled = false;
  }
});
window.addEventListener('keydown', async (event) => {
  if (!device) {
    return;
  }
  let data: any;
  if (event.key.length === 1) {
    data = new Int8Array([event.key.charCodeAt(0)]);
  } else if (event.code === 'Enter') {
    data = new Uint8Array([0x0a]);
  } else {
    return;
  }
  await device.transferOut(ep, data);
}, true);

let haltButton = document.getElementById('haltButton') as HTMLButtonElement;
haltButton.addEventListener('click', () => {
  halt = true;
  button.disabled = false;
  requestSerialButton.disabled = false;
});

let ranges = [];
function paintHistogram(t0: number, t1: number) {
  // constants
  const xtick = 40;
  const boxWidth = 10;

  // setup a graph (drop if exists)
  const margin = {top: 40, right: 40, bottom: 100, left: 100};
  const width = 1000 - margin.left - margin.right;
  const height = 1000 - margin.top - margin.bottom;
  const svg =
      d3.select('#my_dataviz')
          .html('')
          .append('svg')
          .attr('width', width + margin.left + margin.right)
          .attr('height', height + margin.top + margin.bottom)
          .append('g')
          .attr(
              'transform', 'translate(' + margin.left + ',' + margin.top + ')');

  // y axis and its label
  const dataAll: Array<number> = currentData.map((e: (Date|number)) => e[1] as number);
  const ymin = d3.min(dataAll) - 1000;
  const ymax = d3.max(dataAll) + 1000;
  const y = d3.scaleLinear().domain([ymax, ymin]).range([0, height]);
  svg.append('g').call(d3.axisLeft(y));
  svg.append('text')
      .attr('text-anchor', 'end')
      .attr('transform', 'rotate(-90)')
      .attr('y', -margin.left + 20)
      .attr('x', -margin.top)
      .text('Power (mW)');

  ranges.push([t0, t1]);

  for (let i = 0; i < ranges.length; i++) {
    // compute data and place of i-th series
    const left = ranges[i][0];
    const right = ranges[i][1];
    let points = currentData.filter(
        (e: (Date|String)) =>
            (left <= e[0].getTime() && e[0].getTime() <= right));
    let data: Array<number> = points.map((e: (Date|number)) => e[1] as number);
    const center = xtick * (i + 1);

    // Compute statistics
    const data_sorted = data.sort(d3.ascending);
    const q1 = d3.quantile(data_sorted, .25);
    const median = d3.quantile(data_sorted, .5);
    const q3 = d3.quantile(data_sorted, .75);
    const interQuantileRange = q3 - q1;
    const lowerFence = q1 - 1.5 * interQuantileRange;
    const upperFence = q3 + 1.5 * interQuantileRange;
    const minValue = d3.min(data);
    const maxValue = d3.max(data);
    const mean = d3.mean(data);


    // min, mean, max
    svg.append('line')
        .attr('x1', center)
        .attr('x2', center)
        .attr('y1', y(minValue))
        .attr('y2', y(maxValue))
        .style('stroke-dasharray', '3, 3')
        .attr('stroke', 'gray')
    svg.selectAll('toto')
        .data([minValue, mean, maxValue])
        .enter()
        .append('line')
        .attr('x1', center - boxWidth)
        .attr('x2', center + boxWidth)
        .attr(
            'y1',
            function(d) {
              return (y(d))
            })
        .attr(
            'y2',
            function(d) {
              return (y(d))
            })
        .style('stroke-dasharray', '3, 3')
        .attr('stroke', 'gray');

    // box and line
    svg.append('line')
        .attr('x1', center)
        .attr('x2', center)
        .attr('y1', y(lowerFence))
        .attr('y2', y(upperFence))
        .attr('stroke', 'black')
    svg.append('rect')
        .attr('x', center - boxWidth / 2)
        .attr('y', y(q3))
        .attr('height', (y(q1) - y(q3)))
        .attr('width', boxWidth)
        .attr('stroke', 'black')
        .style('fill', '#69b3a2')
    svg.selectAll('toto')
        .data([lowerFence, median, upperFence])
        .enter()
        .append('line')
        .attr('x1', center - boxWidth / 2)
        .attr('x2', center + boxWidth / 2)
        .attr(
            'y1',
            function(d) {
              return (y(d))
            })
        .attr(
            'y2',
            function(d) {
              return (y(d))
            })
        .attr('stroke', 'black');
  }
}

function setupAnalyze() {
  const button = document.createElement('button');
  button.innerText = 'Analyze displayed range';
  controlDiv.appendChild(button);
  button.addEventListener('click', () => {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    let xrange = g.xAxisRange();
    let left = xrange[0];
    let right = xrange[1];
    paintHistogram(left, right);
  });
}
setupAnalyze();

function setupDataLoad() {
  const handleFileSelect = (evt: DragEvent) => {
    evt.stopPropagation();
    evt.preventDefault();
    const file = evt.dataTransfer.files[0];
    if (file === undefined) {
      return;
    }
    const r = new FileReader();
    r.addEventListener('load', () => {
      const data = JSON.parse(r.result as string);
      console.log(data);
      const powerData = data.power.map((d: string) => [new Date(d[0]), d[1]])
      updateGraph(powerData);
    })
    r.readAsText(file);
  };

  const handleDragOver = (evt: DragEvent) => {
    evt.stopPropagation();
    evt.preventDefault();
    evt.dataTransfer.dropEffect = 'copy';  // Explicitly show this is a copy.
  };
  const dropZone = document.createElement('span');
  dropZone.innerText = 'Drop .json here';
  dropZone.className = 'dropzone'
  document.body.appendChild(dropZone);
  dropZone.addEventListener('dragover', handleDragOver, false);
  dropZone.addEventListener('drop', handleFileSelect, false);
}
setupDataLoad();
