export class OperatePort {
  private port?: SerialPort;
  private reader = new ReadableStreamDefaultReader(new ReadableStream());
  private usbVendorId: number;
  private usbProductId: number;
  private encoder = new TextEncoder();
  private decoder = new TextDecoder();
  constructor(usbVendorId: number, usbProductId: number) {
    this.usbVendorId = usbVendorId;
    this.usbProductId = usbProductId;
  }
  public async open() {
    this.port = await navigator.serial
      .requestPort({
        filters: [
          {usbVendorId: this.usbVendorId, usbProductId: this.usbProductId},
        ],
      })
      .catch(e => {
        console.error(e);
        throw e;
      });
    await this.port.open({baudRate: 115200});
  }
  public async closeWhileReading() {
    if (this.port === undefined) return;
    await this.reader.cancel();
    await this.reader.releaseLock();
    await this.port.close();
  }
  public async close() {
    if (this.port === undefined) return;
    await this.port.close();
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
