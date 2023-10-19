const encoder = new TextEncoder();
const utf8decoder = new TextDecoder('utf-8');

let servoPort: SerialPort;
let servoReader: ReadableStreamDefaultReader;

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
// const usb_interface = 0;
// const ep = usb_interface + 1;

// export async function openUSBPort() {
//   device = await navigator.usb
//     .requestDevice({filters: [{vendorId: 0x18d1, productId: 0x520d}]})
//     .catch(e => {
//       console.error(e);
//       throw e;
//     });
//   await device.open();
//   await device.selectConfiguration(1);
//   await device.claimInterface(usb_interface);
// }

// export function closeUSBPort() {
//   try {
//     device.close();
//   } catch (e) {
//     console.error(e);
//   }
// }

// export async function writeUSBPort(s: Uint8Array) {
//   await device.transferOut(ep, s);
// }

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
