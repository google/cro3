export class operatePort {
  isSerial = true;
  vendorId: number;
  productId: number;
  serial = new (class {
    port?: SerialPort;
    reader = new ReadableStreamDefaultReader(new ReadableStream());
    encoder = new TextEncoder();
    decoder = new TextDecoder();
    async open(usbVendorId: number, usbProductId: number) {
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
    async close() {
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
    async read() {
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
    async write(s: string) {
      if (this.port === undefined) return;
      const writable = this.port.writable;
      if (writable === null) return;
      const writer = writable.getWriter();
      await writer.write(this.encoder.encode(s));
      writer.releaseLock();
    }
  })();
  usb = new (class {
    halt = false;
    device?: USBDevice;
    usb_interface = 0;
    ep = this.usb_interface + 1;
    encoder = new TextEncoder();
    decoder = new TextDecoder();
    changeHaltFlag(flag: boolean) {
      this.halt = flag;
    }
    async open(vendorId: number, productId: number) {
      this.device = await navigator.usb
        .requestDevice({filters: [{vendorId: vendorId, productId: productId}]})
        .catch(e => {
          console.error(e);
          throw e;
        });
      await this.device.open();
      await this.device.selectConfiguration(1);
      await this.device.claimInterface(this.usb_interface);
    }
    async close() {
      if (this.device === undefined) return;
      try {
        await this.device.close();
      } catch (e) {
        console.error(e);
      }
    }
    async read() {
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
        if (!this.halt) {
          console.error(e);
          throw e;
        }
        return '';
      }
    }
    async write(s: string) {
      if (this.device === undefined) return;
      await this.device.transferOut(this.ep, this.encoder.encode(s));
    }
  })();
  constructor(vendorId: number, productId: number) {
    this.vendorId = vendorId;
    this.productId = productId;
  }
  async setIsSerialFlag(isSerial: boolean) {
    this.isSerial = isSerial;
  }
  async open() {
    if (this.isSerial) await this.serial.open(this.vendorId, this.productId);
    else await this.usb.open(this.vendorId, this.productId);
  }
  async close() {
    if (this.isSerial) await this.serial.close();
    else await this.usb.close();
  }
  async read() {
    if (this.isSerial) return await this.serial.read();
    else return await this.usb.read();
  }
  async write(s: string) {
    if (this.isSerial) await this.serial.write(s);
    else await this.usb.write(s);
  }
}
