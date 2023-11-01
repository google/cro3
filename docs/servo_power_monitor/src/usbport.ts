export class usbPort {
  halt: boolean;
  device?: USBDevice;
  usb_interface = 0;
  ep = this.usb_interface + 1;
  encoder = new TextEncoder();
  decoder = new TextDecoder();
  constructor(halt: boolean) {
    this.halt = halt;
  }
  async open() {
    this.device = await navigator.usb
      .requestDevice({filters: [{vendorId: 0x18d1, productId: 0x520d}]})
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
}
