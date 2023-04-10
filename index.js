const ctx = document.getElementById('myChart');

//const rawData = Array.from({ length: 100 }, (v, i) => {return {x: i, y: 0}});
//let dataIndex = 0;
const rawData = [];

const data = {
  datasets:
      [{label: 'Power (mW)', data: rawData, backgroundColor: 'rgb(255, 99, 132)'}],
};
const config = {
  type: 'scatter',
  data: data,
  options: {
    scales: {x: {position: 'bottom'}},
  },
};
config.options.animation = false;
const chart = new Chart(ctx, config);

const utf8decoder = new TextDecoder();  // default 'utf-8' or 'utf8'

const requestSerialButton = document.getElementById('requestSerialButton');
requestSerialButton.addEventListener('click', () => {
  navigator.serial
      .requestPort({filters: [{usbVendorId: 0x18d1, usbProductId: 0x520d}]})
      .then(async (port) => {
        // Connect to `port` or add it to the list of available ports.
        await port.open({baudRate: 115200});
        console.log(port);
        const encoder = new TextEncoder();
        const writer = port.writable.getWriter();
        await writer.write(encoder.encode('help\n'));
        writer.releaseLock();

        // Launch write loop
        const f = async (event) => {
          console.log(`On connect!: ${event}`)
          while (true) {
            let data = new TextEncoder().encode('ina 0\n');
            const writer = port.writable.getWriter();
            await writer.write(data);
            writer.releaseLock();
            await new Promise(r => setTimeout(r, 100));
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
                console.log(value);
                serial_output.innerText += utf8decoder.decode(value);

                let output = serial_output.innerText;

                let splitted =
                    output.split('\n').filter((s) => s.trim().length > 10);
                if (splitted.length > 0 &&
                    splitted[splitted.length - 1].indexOf('Alert limit') >= 0) {
                  console.log(output);
                  let power = splitted.find((s) => s.startsWith('Power'));
                  power = power.split('=>')[1].trim();
                  power = power.split(' ');
                  console.log(power);
                  power = parseInt(power[0]);
                  //chart.data.datasets[0].data[dataIndex++] = {x: dataIndex, y: power};
                  chart.data.datasets[0].data.push({x: new Date(), y: power});
                  //dataIndex %= chart.data.datasets[0].data.length;
                  chart.update('none');

                  serial_output.innerText = '';
                }
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

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
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
    console.log(device);
    await device.selectConfiguration(1);
    await device.claimInterface(interface);

    const f = async (event) => {
      console.log(`On connect!: ${event}`)
      while (true) {
        let data = new TextEncoder().encode('ina 0\n');
        await device.transferOut(ep, data);
        await new Promise(r => setTimeout(r, 1000));
      }
    };
    setTimeout(f, 1000);

    while (true) {
      let result = await device.transferIn(ep, 64);
      result = new Int8Array(result.data.buffer);

      serial_output.innerText += utf8decoder.decode(result);

      let output = serial_output.innerText;

      let splitted = output.split('\n').filter((s) => s.trim().length > 10);
      if (splitted.length > 0 &&
          splitted[splitted.length - 1].indexOf('Alert limit') >= 0) {
        console.log(output);
        let power = splitted.find((s) => s.startsWith('Power'));
        power = power.split('=>')[1].trim();
        power = power.split(' ');
        console.log(power);
        power = parseInt(power[0]);
        chart.data.datasets[0].data.push({x: new Date(), y: power});
        chart.update();

        serial_output.innerText = '';
      }
      window.scrollTo(document.body.scrollWidth, document.body.scrollHeight);

      if (result.status === 'stall') {
        console.warn('Endpoint stalled. Clearing.');
        await device.clearHalt(1);
      }
      await new Promise(r => setTimeout(r, 100));
    }
  } catch (err) {
    console.log(`Disconnected: ${err}`);
    device = null;
    button.disabled = false;
  }
});
window.addEventListener('keydown', async (event) => {
  console.log(`KeyboardEvent: key='${event.key}' | code='${event.code}'`);
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
  console.log(data);
  await device.transferOut(ep, data);
}, true);
