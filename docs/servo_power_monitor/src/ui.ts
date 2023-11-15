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
    }
    return shellScriptContents;
  }
  public addConfigInputArea() {
    const newConfigListElem = document.createElement('li');
    newConfigListElem.innerHTML =
      '<label>script:</label><textarea>sleep 3</textarea><button>delete</button>';
    this.shellScriptList.appendChild(newConfigListElem);
    const newButtonElem = newConfigListElem.querySelector(
      'button'
    ) as HTMLButtonElement;
    newButtonElem.addEventListener('click', () => {
      this.configNum -= 1;
      newConfigListElem.remove();
    });
    this.configNum += 1;
  }
  public createGraphList() {
    for (let i = 0; i < this.configNum; i++) {
      const newGraphListElem = document.createElement('li');
      newGraphListElem.innerHTML = `<div id="graph${i}"></div>`;
      this.graphList.appendChild(newGraphListElem);
    }
  }
  public addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
