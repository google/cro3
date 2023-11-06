type parseData = {
  power: number;
  originalData: string;
};

export class DataParser {
  private output = '';
  public async readData(readFn: () => Promise<string>) {
    for (;;) {
      try {
        const s = await readFn();
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
        // break the loop here because `disconnect` event is not called in Chrome
        // for some reason when the loop continues. And no need to throw error
        // here because it is thrown in readFn.
        return undefined;
      }
    }
  }
}
