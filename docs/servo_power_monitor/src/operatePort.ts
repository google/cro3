interface PortInterface {
  open: (usbVendorId: number, usbProductId: number) => Promise<void>;
  close: () => Promise<void>;
  read: () => Promise<string>;
  write: (s: string) => Promise<void>;
}

class OperateSerialPort implements PortInterface {
  private port?: SerialPort;
  private reader = new ReadableStreamDefaultReader(new ReadableStream());
  private encoder = new TextEncoder();
  private decoder = new TextDecoder();
  public async open(usbVendorId: number, usbProductId: number) {
    this.port = await navigator.serial
      .requestPort({
        filters: [{usbVendorId: usbVendorId, usbProductId: usbProductId}],
      })
      .catch(e => {
        console.error(e);
        throw e;
      });
    await this.port.open({baudRate: 115200});
  }
  public async close() {
    if (this.port === undefined) return;
    await this.reader.cancel();
    await this.reader.releaseLock();
    try {
      await this.port.close();
    } catch (e) {
      console.error(e);
      throw e;
    }
  }
  public async read() {
    if (this.port === undefined) return '';
    const readable = this.port.readable;
    if (readable === null) return '';
    this.reader = readable.getReader();
    try {
      for (;;) {
        const {value, done} = await this.reader.read();
        if (done) {
          // |reader| has been canceled.
          this.reader.releaseLock();
          return '';
        }
        return this.decoder.decode(value);
      }
    } catch (error) {
      this.reader.releaseLock();
      console.error(error);
      throw error;
    } finally {
      this.reader.releaseLock();
    }
  }
  public async write(s: string) {
    if (this.port === undefined) return;
    const writable = this.port.writable;
    if (writable === null) return;
    const writer = writable.getWriter();
    await writer.write(this.encoder.encode(s));
    writer.releaseLock();
  }
}

class OperateUsbPort implements PortInterface {
  halt = false;
  private device?: USBDevice;
  private usb_interface = 0;
  private ep = this.usb_interface + 1;
  private encoder = new TextEncoder();
  private decoder = new TextDecoder();
  changeHaltFlag(flag: boolean) {
    this.halt = flag;
  }
  public async open(vendorId: number, productId: number) {
    this.device = await navigator.usb
      .requestDevice({
        filters: [{vendorId: vendorId, productId: productId}],
      })
      .catch(e => {
        console.error(e);
        throw e;
      });
    await this.device.open();
    await this.device.selectConfiguration(1);
    await this.device.claimInterface(this.usb_interface);
  }
  public async close() {
    if (this.device === undefined) return;
    try {
      await this.device.close();
    } catch (e) {
      console.error(e);
    }
  }
  public async read() {
    if (this.device === undefined) return '';
    try {
      const result = await this.device.transferIn(this.ep, 64);
      if (result.status === 'stall') {
        await this.device.clearHalt('in', this.ep);
        throw result;
      }
      const resultData = result.data;
      if (resultData === undefined) return '';
      const result_array = new Int8Array(resultData.buffer);
      return this.decoder.decode(result_array);
    } catch (e) {
      // If halt is true, it's when the stop button is pressed. Therefore,
      // we can ignore the error.

      // NOTE: investigate the way not to use halt flag because it makes the implementation complicated
      // if (!this.halt) {
      if (this.device.opened) {
        console.error(e);
        throw e;
      }
      return '';
    }
  }
  public async write(s: string) {
    if (this.device === undefined) return;
    await this.device.transferOut(this.ep, this.encoder.encode(s));
  }
}

export class OperatePort {
  private vendorId: number;
  private productId: number;
  private currentDevice?: OperateSerialPort | OperateUsbPort;
  public isSerial = false;
  constructor(vendorId: number, productId: number) {
    this.vendorId = vendorId;
    this.productId = productId;
  }
  public async open(isSerial: boolean) {
    if (isSerial) {
      this.currentDevice = new OperateSerialPort();
    } else {
      this.currentDevice = new OperateUsbPort();
    }
    await this.currentDevice.open(this.vendorId, this.productId);
    this.isSerial = isSerial;
  }
  public async close() {
    if (this.currentDevice === undefined) return;
    this.currentDevice.close();
  }
  public async read() {
    if (this.currentDevice === undefined) return '';
    return this.currentDevice.read();
  }
  public async write(s: string) {
    if (this.currentDevice === undefined) return;
    this.currentDevice.write(s);
  }
}
