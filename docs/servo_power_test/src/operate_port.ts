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
  public async select() {
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
  }
  public async open() {
    if (this.port === undefined) return;
    await this.port.open({baudRate: 115200});
  }
  public async readCancel() {
    await this.reader
      .cancel()
      .then(() => {
        this.reader.releaseLock();
      })
      .catch(() => {}); // when the reader stream is already locked, do nothing.
  }
  public async close() {
    if (this.port === undefined) return;
    await this.readCancel();
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
        return this.decoder.decode(value, {stream: true});
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
    try {
      await writer.write(this.encoder.encode(s));
    } catch (error) {
      writer.releaseLock();
      console.error(error);
      throw error;
    } finally {
      writer.releaseLock();
    }
  }
}
