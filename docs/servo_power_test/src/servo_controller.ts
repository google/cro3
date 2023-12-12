import {OperatePort} from './operate_port';

type parseData = {
  power: number;
  originalData: string;
};

export class ServoController {
  // ina 0 and 1 seems to be the same
  // ina 2 is something but not useful
  private INA_COMMAND = 'ina 0\n';
  private isOpened = false;
  private output = '';
  public servoShell = new OperatePort(0x18d1, 0x520d);
  public halt = true;
  public async openServoPort() {
    if (this.isOpened) return;
    await this.servoShell.open();
    this.isOpened = true;
  }
  public async closeServoPort() {
    if (!this.isOpened) return;
    await this.servoShell.close();
    this.isOpened = false;
  }
  public async readData() {
    for (;;) {
      if (this.halt) return undefined;
      try {
        const s = await this.servoShell.read();
        this.output += s;
        const splitted = this.output
          .split('\n')
          .filter(s => s.trim().length > 10);
        if (
          splitted.length > 0 &&
          splitted[splitted.length - 1].indexOf('Alert limit') >= 0
        ) {
          const powerString = splitted.find(s => s.startsWith('Power'));
          if (powerString === undefined) return undefined;
          const power = parseInt(
            powerString.split('=>')[1].trim().split(' ')[0]
          );
          const parseResult: parseData = {
            power: power,
            originalData: this.output,
          };
          this.output = '';
          return parseResult;
        }
      } catch (e) {
        console.error(e);
        throw e;
      }
    }
  }
  public async writeInaCommand() {
    await this.servoShell.write(this.INA_COMMAND);
  }
}
