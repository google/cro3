export class serialPort {
  port: SerialPort | undefined = undefined;
  reader = new ReadableStreamDefaultReader(new ReadableStream());
  encoder = new TextEncoder();
  decoder = new TextDecoder();
  open = async (usbVendorId: number, usbProductId: number) => {
    this.port = await navigator.serial
      .requestPort({
        filters: [{usbVendorId: usbVendorId, usbProductId: usbProductId}],
      })
      .catch(e => {
        console.error(e);
        throw e;
      });
    await this.port.open({baudRate: 115200});
  };
  close = async () => {
    if (this.port === undefined) return;
    await this.reader.cancel();
    await this.reader.releaseLock();
    try {
      await this.port.close();
    } catch (e) {
      console.error(e);
      throw e;
    }
  };
  read = async () => {
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
  };
  write = async (s: string) => {
    if (this.port === undefined) return;
    const writable = this.port.writable;
    if (writable === null) return;
    const writer = writable.getWriter();
    await writer.write(this.encoder.encode(s));
    writer.releaseLock();
  };
}
