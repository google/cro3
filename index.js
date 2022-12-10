function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
// https://wicg.github.io/webusb/
let button = document.getElementById('request-device');
let serial_output = document.getElementById('serial_output');
let device;
let interface = 0;  // 1: AP Console
let ep = interface + 1;
button.addEventListener('click', async () => {
  device = null;
  button.disabled = true;
  try {
    device = await navigator.usb.requestDevice({
      filters: [{
        vendorId: 0x18d1,  /* Google */
        productId: 0x5014, /* Cr50 */
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

    while (true) {
      let result = await device.transferIn(ep, 64);
      result = new Int8Array(result.data.buffer);

      serial_output.innerText += utf8decoder.decode(result);

      window.scrollTo(0, document.body.scrollHeight);

      if (result.status === 'stall') {
        console.warn('Endpoint stalled. Clearing.');
        await device.clearHalt(1);
      }
    }
  } catch (err) {
    console.log(`Disconnected: ${err}`);
    device = null;
    button.disabled = false;
  }
});
navigator.usb.addEventListener(
    'connect', (event) => {console.log(`On connect!: ${event}`)});
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
