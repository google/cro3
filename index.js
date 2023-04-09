function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
// https://wicg.github.io/webusb/
let button = document.getElementById('request-device');
let serial_output = document.getElementById('serial_output');
let device;
let interface = 0;
let ep = interface + 1;
/*
 Servo
 interface 0 : servo console

 */
button.addEventListener('click', async () => {
  device = null;
  button.disabled = true;
  try {
    device = await navigator.usb.requestDevice({
      filters: [{
        vendorId: 0x18d1, /* Google */
        // productId: 0x5014, /* Cr50 */
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
    if (device.configuration === null) await device.selectConfiguration(1);
    await device.claimInterface(interface);
    let utf8decoder = new TextDecoder();  // default 'utf-8' or 'utf8'

      const f = 
    async (event) => {console.log(`On connect!: ${event}`)
while (true) {
  let data = new TextEncoder().encode("ina 0\n");
  await device.transferOut(ep, data);
  await new Promise(r => setTimeout(r, 1000));
}
    };
    setTimeout(f, 1000);

    while (true) {
      let result = await device.transferIn(ep, 64);
      result = new Int8Array(result.data.buffer);

      serial_output.innerText += utf8decoder.decode(result);

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
