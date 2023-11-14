export class Ui {
  public requestSerialButton = document.getElementById(
    'request-serial-button'
  ) as HTMLButtonElement;
  public haltButton = document.getElementById(
    'halt-button'
  ) as HTMLButtonElement;
  public downloadButton = document.getElementById(
    'download-button'
  ) as HTMLButtonElement;
  public analyzeButton = document.getElementById(
    'analyze-button'
  ) as HTMLButtonElement;
  public selectDutSerialButton = document.getElementById(
    'select-dut-serial-button'
  ) as HTMLButtonElement;
  private shellScript = document.getElementById(
    'shellScript'
  ) as HTMLDivElement;
  public shellScriptInput = document.getElementById(
    'shell-script-input'
  ) as HTMLTextAreaElement;
  public addConfigButton = document.getElementById(
    'addConfigButton'
  ) as HTMLButtonElement;
  public dutCommandForm = document.getElementById(
    'dut-command-form'
  ) as HTMLFormElement;
  public dutCommandInput = document.getElementById(
    'dut-command-input'
  ) as HTMLInputElement;
  public popupCloseButton = document.getElementById(
    'popup-close'
  ) as HTMLButtonElement;
  public overlay = document.getElementById('popup-overlay') as HTMLDivElement;
  public messages = document.getElementById('messages') as HTMLDivElement;
  public executeScriptButton = document.getElementById(
    'execute-script-button'
  ) as HTMLButtonElement;
  public dropZone = document.getElementById('drop-zone') as HTMLSpanElement;
  public serialOutput = document.getElementById(
    'serial-output'
  ) as HTMLDivElement;
  public dlAnchorElem = document.getElementById(
    'download-anchor'
  ) as HTMLAnchorElement;
  public toolTip = document.getElementById('tooltip') as HTMLDivElement;
  public configNum = 1;

  public enabledRecordingButton(halt: boolean) {
    this.requestSerialButton.disabled = !halt;
    this.haltButton.disabled = halt;
    this.downloadButton.disabled = !halt;
    this.analyzeButton.disabled = !halt;
  }
  public setSerialOutput(s: string) {
    this.serialOutput.textContent = s;
  }
  public readInputValue() {
    const res = this.dutCommandInput.value;
    this.dutCommandInput.value = '';
    return res;
  }
  public readInputShellScript() {
    const textAreas = this.shellScript.getElementsByTagName(
      'textarea'
    ) as HTMLCollectionOf<HTMLTextAreaElement>;
    const shellScriptContents: Array<string> = [];
    for (let i = 0; i < textAreas.length; i++) {
      shellScriptContents.push(textAreas[i].value);
      console.log(textAreas[i].value);
    }
    return shellScriptContents;
  }
  public addConfigInputArea() {
    this.configNum += 1;
    const newLabelElem = document.createElement('label');
    newLabelElem.textContent = `config+workload(${this.configNum}):`;
    const newTextAreaElem = document.createElement('textarea');
    newLabelElem.appendChild(newTextAreaElem);
    this.shellScript.appendChild(newLabelElem);
  }
  public addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
