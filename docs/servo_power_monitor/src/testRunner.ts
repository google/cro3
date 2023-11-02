import {operatePort} from './operatePort';

export class testRunner {
  isOpened = false;
  CANCEL_CMD = '\x03\n';

  port: operatePort;
  constructor(port: operatePort) {
    this.port = port;
  }
  async selectPort(addMessageToConsole: (s: string) => void) {
    await this.port.open();
    this.isOpened = true;
    addMessageToConsole('DutPort is selected');
    for (;;) {
      const chunk = await this.port.read();
      addMessageToConsole(chunk);
    }
  }
  async executeScript(script: string) {
    await this.port.write('cat > ./example.sh << EOF\n');
    await this.port.write(script);
    await this.port.write('EOF\n');
    await this.port.write('bash ./example.sh\n');
  }
  async sendCommand(s: string) {
    await this.port.write(s);
  }
}
