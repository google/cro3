import Dygraph from 'dygraphs';
import moment from 'moment';

const intervalMs = 100;

let powerData = [];
const g = new Dygraph('graph', powerData, {});

const utf8decoder = new TextDecoder();  // default 'utf-8' or 'utf8'

let output = '';
let halt = false;
function pushOutput(s: string) {
  output += s

  let splitted = output.split('\n').filter((s) => s.trim().length > 10);
  if (splitted.length > 0 &&
      splitted[splitted.length - 1].indexOf('Alert limit') >= 0) {
    let power = parseInt(splitted.find((s) => s.startsWith('Power'))
                             .split('=>')[1]
                             .trim()
                             .split(' ')[0]);
    let p = {x: new Date(), y: power};
    powerData.push([p.x, p.y]);
    g.updateOptions(
        {
          file: powerData,
          labels: ['t', 'Power(mW)'],
          showRoller: true,
          // customBars: true,
          ylabel: 'Power (mW)',
          legend: 'always',
        },
        false);
    serial_output.innerText = output;
    output = '';
  }
}

const requestSerialButton = document.getElementById('requestSerialButton') as HTMLButtonElement;
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

let downloadButton = document.getElementById('downloadButton') as HTMLButtonElement;
downloadButton.addEventListener('click', async () => {
  var dataStr = 'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify(powerData));
  var dlAnchorElem = document.getElementById('downloadAnchorElem');
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

    const f = async (_event : any) => {
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

