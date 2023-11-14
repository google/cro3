export class Ui {
  public requestSerialButton = document.getElementById(
    'requestSerialButton'
  ) as HTMLButtonElement;
  public haltButton = document.getElementById(
    'haltButton'
  ) as HTMLButtonElement;
  public downloadButton = document.getElementById(
    'downloadButton'
  ) as HTMLButtonElement;
  public analyzeButton = document.getElementById(
    'analyzeButton'
  ) as HTMLButtonElement;
  public selectDutSerialButton = document.getElementById(
    'selectDutSerialButton'
  ) as HTMLButtonElement;
  private shellScriptList = document.getElementById(
    'shellScriptList'
  ) as HTMLUListElement;
  public shellScriptInput = document.getElementById(
    'shellScriptInput'
  ) as HTMLTextAreaElement;
  public addConfigButton = document.getElementById(
    'addConfigButton'
  ) as HTMLButtonElement;
  public deleteConfigButton = document.getElementById(
    'deleteConfigButton'
  ) as HTMLButtonElement;
  public dutCommandForm = document.getElementById(
    'dutCommandForm'
  ) as HTMLFormElement;
  public dutCommandInput = document.getElementById(
    'dutCommandInput'
  ) as HTMLInputElement;
  public popupCloseButton = document.getElementById(
    'popup-close'
  ) as HTMLButtonElement;
  public overlay = document.getElementById('popup-overlay') as HTMLDivElement;
  public messages = document.getElementById('messages') as HTMLDivElement;
  public executeScriptButton = document.getElementById(
    'executeScriptButton'
  ) as HTMLButtonElement;
  public dropZone = document.getElementById('dropZone') as HTMLSpanElement;
  public serial_output = document.getElementById(
    'serial_output'
  ) as HTMLDivElement;
  public dlAnchorElem = document.getElementById(
    'downloadAnchorElem'
  ) as HTMLAnchorElement;
  public toolTip = document.getElementById('tooltip') as HTMLDivElement;
  private graphList = document.getElementById('graphList') as HTMLUListElement;
  public configNum = 1;

  public enabledRecordingButton(halt: boolean) {
    this.requestSerialButton.disabled = !halt;
    this.haltButton.disabled = halt;
    this.downloadButton.disabled = !halt;
    this.analyzeButton.disabled = !halt;
  }
  public setSerialOutput(s: string) {
    this.serial_output.textContent = s;
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
    if (this.configNum <= 1) return;
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
