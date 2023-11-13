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
  public shellScriptInput = document.getElementById(
      'shellScriptInput'
    ) as HTMLTextAreaElement;
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
  public readInputScript() {
    return this.shellScriptInput.value;
  }
  public addMessageToConsole(s: string) {
    this.messages.textContent += s;
    this.messages.scrollTo(0, this.messages.scrollHeight);
  }
  public hideToolTip() {
    this.toolTip.classList.add('hidden');
  }
}
