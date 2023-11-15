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
  public configNum = 0;

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
    const newConfigListElem = document.createElement('li');
    newConfigListElem.id = `shellScript${this.configNum}`;
    newConfigListElem.innerHTML =
      '<label>script:</label><textarea>sleep 3</textarea><button>delete</button>';
    this.shellScriptList.appendChild(newConfigListElem);
    const newGraphListElem = document.createElement('li');
    newGraphListElem.innerHTML = `<div id="graph${this.configNum}"></div>`;
    this.graphList.appendChild(newGraphListElem);

    const newButtonElem = newConfigListElem.querySelector(
      'button'
    ) as HTMLButtonElement;
    newButtonElem.addEventListener('click', () => {
      this.configNum -= 1;
      newConfigListElem.remove();
      newGraphListElem.remove();
    });
    this.configNum += 1;
  }
  public addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
