const intervalMs = 100;
const avgWindow = 9;
const avgWindow2 = 41;

const ctx = document.getElementById('myChart');
ctx.width = 1024;
ctx.height = 768

const data = {
  datasets: [
    {
      label: 'Power (mW)',
      data: [],
      backgroundColor: 'rgb(255, 99, 132)',
      pointStyle: 'circle',
      pointRadius: 1,
      order: 3,
    },
    {
      label: `Power avg (mW) (window = ${avgWindow})`,
      data: [],
      backgroundColor: 'rgb(99, 255, 132)',
      borderColor: 'rgb(0, 255, 0)',
      showLine: true,
      order: 2,
      pointStyle: 'false',
    },
    {
      label: `Power avg (mW) (window = ${avgWindow2})`,
      data: [],
      backgroundColor: 'rgb(0, 0, 255)',
      borderColor: 'rgb(0, 0, 255)',
      showLine: true,
      order: 1,
      pointStyle: 'false',
    },
  ],
};
const config = {
  type: 'scatter',
  data: data,
  options: {
    scales: {
      y: {
        suggestedMin: 0,
        suggestedMax: 30 * 1000,
      },
      x: {position: 'bottom'},
    },
    animation: false,
    responsive: false,
    plugins: {
      tooltip: {
        enabled: false,
      }
    }
  },
};
const chart = new Chart(ctx, config);

const utf8decoder = new TextDecoder();  // default 'utf-8' or 'utf8'

let output = '';
let avgPoints = [];
let avgPoints2 = [];
function pushOutput(s) {
  output += s

  let splitted = output.split('\n').filter((s) => s.trim().length > 10);
  if (splitted.length > 0 &&
      splitted[splitted.length - 1].indexOf('Alert limit') >= 0) {
    let power = splitted.find((s) => s.startsWith('Power'));
    power = power.split('=>')[1].trim();
    power = power.split(' ');
    power = parseInt(power[0]);
    // chart.data.datasets[0].data[dataIndex++] = {x: dataIndex, y: power};
    let p = {x: new Date(), y: power};
    chart.data.datasets[0].data.push(p);
    avgPoints.push(p);
    avgPoints2.push(p);
    if (avgPoints.length == avgWindow) {
      let sum = avgPoints.reduce((l, r) => l + r.y, 0);
      let avg = sum / avgWindow;
      chart.data.datasets[1].data.push({x: avgPoints[(avgWindow/2) | 0].x, y: avg});
      avgPoints = [];
    }
    if (avgPoints2.length == avgWindow2) {
      let sum = avgPoints2.reduce((l, r) => l + r.y, 0);
      let avg = sum / avgWindow2;
      chart.data.datasets[2].data.push({x: avgPoints2[(avgWindow/2) | 0].x, y: avg});
      avgPoints2 = [];
    }
    chart.update('none');
    serial_output.innerText = output;
    output = '';
  }
}

const requestSerialButton = document.getElementById('requestSerialButton');
requestSerialButton.addEventListener('click', () => {
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
        const f = async (event) => {
          while (true) {
            let data = new TextEncoder().encode('ina 0\n');
            const writer = port.writable.getWriter();
            await writer.write(data);
            writer.releaseLock();
            await new Promise(r => setTimeout(r, intervalMs));
          }
        };
        setTimeout(f, 1000);

        // read loop
        for (;;) {
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

let button = document.getElementById('request-device');
let serial_output = document.getElementById('serial_output');
let device;
let interface = 0;
let ep = interface + 1;
button.addEventListener('click', async () => {
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
    await device.claimInterface(interface);

    const f = async (_event) => {
      while (true) {
        let data = new TextEncoder().encode('ina 0\n');
        await device.transferOut(ep, data);
        await new Promise(r => setTimeout(r, intervalMs));
      }
    };
    setTimeout(f, intervalMs);

    while (true) {
      let result = await device.transferIn(ep, 64);
      if (result.status === 'stall') {
        await device.clearHalt(1);
        continue;
      }
      result = new Int8Array(result.data.buffer);
      pushOutput(utf8decoder.decode(result));
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
  let data;
  if (event.key.length === 1) {
    data = new Int8Array([event.key.charCodeAt(0)]);
  } else if (event.code === 'Enter') {
    data = new Uint8Array([0x0a]);
  } else {
    return;
  }
  await device.transferOut(ep, data);
}, true);
