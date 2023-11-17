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
  public popupCloseButton = document.getElementById(
    'popup-close'
  ) as HTMLButtonElement;
  public overlay = document.getElementById('popup-overlay') as HTMLDivElement;
  public dut_console = document.getElementById('dut_console') as HTMLSpanElement;
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
  }
  public setSerialOutput(s: string) {
    this.serial_output.textContent = s;
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
      `<label>script:</label><textarea>stress-ng -c ${this.configNum+1} -t 10</textarea><button>delete</button>`;
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
  public loadConfigInputArea(config: string) {
    const newConfigListElem = document.createElement('li');
    newConfigListElem.innerHTML =
      `<label>script:</label><textarea>${config}</textarea><button>delete</button>`;
    this.shellScriptList.appendChild(newConfigListElem);
  }
  public createGraphList() {
    for (let i = 0; i < this.configNum; i++) {
      const newGraphListElem = document.createElement('li');
      newGraphListElem.innerHTML = `<div id="graph${i}"></div>`;
      this.graphList.appendChild(newGraphListElem);
    }
  }
  public addMessageToConsole(s: string) {
    this.dut_console.textContent += s;
    this.dut_console.scrollTo(0, this.dut_console.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
