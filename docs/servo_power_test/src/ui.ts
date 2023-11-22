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
  private shellScriptList = document.getElementById(
    'shell-script-list'
  ) as HTMLUListElement;
  public addConfigButton = document.getElementById(
    'add-config-button'
  ) as HTMLButtonElement;
  public dutConsole = document.getElementById('dut-console') as HTMLSpanElement;
  public dropZone = document.getElementById('drop-zone') as HTMLSpanElement;
  public serialOutput = document.getElementById(
    'serial-output'
  ) as HTMLDivElement;
  public dlAnchorElem = document.getElementById(
    'download-anchor'
  ) as HTMLAnchorElement;
  public toolTip = document.getElementById('tooltip') as HTMLDivElement;
  private graphList = document.getElementById('graph-list') as HTMLUListElement;
  public configNum = 0;

  public enabledRecordingButton(halt: boolean) {
    this.requestSerialButton.disabled = !halt;
    this.haltButton.disabled = halt;
    this.downloadButton.disabled = !halt;
  }
  public setSerialOutput(s: string) {
    this.serialOutput.textContent = s;
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
    newConfigListElem.innerHTML = `<label>script:</label><textarea>stress-ng -c ${
      this.configNum + 1
    } -t 10</textarea><button>delete</button>`;
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
    newConfigListElem.innerHTML = `<label>script:</label><textarea>${config}</textarea><button>delete</button>`;
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
    this.dutConsole.textContent += s;
    this.dutConsole.scrollTo(0, this.dutConsole.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
