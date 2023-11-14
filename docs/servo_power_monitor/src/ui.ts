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
  private shellScriptList = document.getElementById(
    'shellScriptList'
  ) as HTMLUListElement;
  public shellScriptInput = document.getElementById(
    'shell-script-input'
  ) as HTMLTextAreaElement;
  public addConfigButton = document.getElementById(
    'addConfigButton'
  ) as HTMLButtonElement;
  public deleteConfigButton = document.getElementById(
    'deleteConfigButton'
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
  private graphList = document.getElementById('graphList') as HTMLUListElement;
  public configNum = 0;

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
    const textAreas = this.shellScriptList.getElementsByTagName(
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
    const newConfigListElem = document.createElement('li');
    const newLabelElem = document.createElement('label');
    newLabelElem.textContent = `config+workload(${this.configNum}):`;
    newConfigListElem.appendChild(newLabelElem);
    const newTextAreaElem = document.createElement('textarea');
    newConfigListElem.appendChild(newTextAreaElem);
    this.shellScriptList.appendChild(newConfigListElem);
    const newGraphListElem = document.createElement('li');
    const newGraphElem = document.createElement('div');
    newGraphElem.id = `graph${this.configNum}`;
    newGraphListElem.appendChild(newGraphElem);
    this.graphList.appendChild(newGraphListElem);
  }
  public deleteConfigInputArea() {
    if (this.configNum <= 0) return;
    if (this.shellScriptList.lastChild === null) return;
    if (this.graphList.lastChild === null) return;
    this.configNum -= 1;
    this.shellScriptList.removeChild(this.shellScriptList.lastChild);
    this.graphList.removeChild(this.graphList.lastChild);
  }
  public addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
