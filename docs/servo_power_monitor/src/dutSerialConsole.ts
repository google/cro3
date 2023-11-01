import {serialPort} from './serialport';

export class dutSerialConsole {
  dut = new serialPort();
  isOpened = false;
  CANCEL_CMD = '\x03\n';
  // shell script
  scripts = `#!/bin/bash -e
function workload () {
  ectool chargecontrol idle
  stress-ng -c 1 -t \\$1
  echo "workload"
}
echo "start"
workload 10 1> ./test_out.log 2> ./test_err.log
echo "end"\n`;
  selectDutSerialButton = document.getElementById(
    'selectDutSerialButton'
  ) as HTMLButtonElement;
  executeScriptButton = document.getElementById(
    'executeScriptButton'
  ) as HTMLButtonElement;
  popupCloseButton = document.getElementById(
    'popup-close'
  ) as HTMLButtonElement;
  dutCommandForm = document.getElementById('dutCommandForm') as HTMLFormElement;
  dutCommandInput = document.getElementById(
    'dutCommandInput'
  ) as HTMLInputElement;
  overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
  messages = document.getElementById('messages') as HTMLDivElement;

  addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }

  readInputValue() {
    const res = this.dutCommandInput.value;
    this.dutCommandInput.value = '';
    return res;
  }

  async selectPort() {
    await this.dut.open(0x18d1, 0x504a);
    this.isOpened = true;
    this.addMessageToConsole('DutPort is selected');
    for (;;) {
      const chunk = await this.dut.read();
      this.addMessageToConsole(chunk);
    }
  }
  async formSubmit(e: Event) {
    e.preventDefault();
    if (!this.isOpened) {
      this.overlay.classList.remove('closed');
      return;
    }
    await this.dut.write(this.readInputValue() + '\n');
  }
  // send cancel command to serial port when ctrl+C is pressed in input area
  async cancelSubmit(e: KeyboardEvent) {
    if (!this.isOpened) {
      this.overlay.classList.remove('closed');
      return;
    }
    if (e.ctrlKey && e.key === 'c') {
      await this.dut.write(this.CANCEL_CMD);
    }
  }
  async executeScript() {
    if (!this.isOpened) {
      this.overlay.classList.remove('closed');
    } else {
      await this.dut.write('cat > ./example.sh << EOF\n');
      await this.dut.write(this.scripts);
      await this.dut.write('EOF\n');
      await this.dut.write('bash ./example.sh\n');
    }
  }
  async disconnectPort() {
    if (this.isOpened) {
      await this.dut.close();
      this.isOpened = false;
    }
  }
  setupHtmlEvent() {
    this.selectDutSerialButton.addEventListener('click', () =>
      this.selectPort()
    );
    this.dutCommandForm.addEventListener('submit', e => this.formSubmit(e));
    this.dutCommandInput.addEventListener('keydown', e => this.cancelSubmit(e));
    this.executeScriptButton.addEventListener('click', () =>
      this.executeScript()
    );
    this.popupCloseButton.addEventListener('click', () => {
      this.overlay.classList.add('closed');
    });
  }
}
