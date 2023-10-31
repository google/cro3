import moment from 'moment';

const requestUsbButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
const downloadButton = document.getElementById(
  'downloadButton'
) as HTMLButtonElement;
const analyzeButton = document.getElementById(
  'analyzeButton'
) as HTMLButtonElement;
const selectDutSerialButton = document.getElementById(
  'selectDutSerialButton'
) as HTMLButtonElement;
const dutCommandForm = document.getElementById(
  'dutCommandForm'
) as HTMLFormElement;
const dutCommandInput = document.getElementById(
  'dutCommandInput'
) as HTMLInputElement;
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
const messages = document.getElementById('messages') as HTMLDivElement;
const executeScriptButton = document.getElementById(
  'executeScriptButton'
) as HTMLButtonElement;
const dropZone = document.getElementById('dropZone') as HTMLSpanElement;

export function requestSerialAddClickEvent(fn: () => Promise<void>) {
  requestSerialButton.addEventListener('click', fn);
}

export function requestUsbAddClickEvent(fn: () => Promise<void>) {
  requestUsbButton.addEventListener('click', fn);
}

export function haltAddClickEvent(fn: () => Promise<void>) {
  haltButton.addEventListener('click', fn);
}

export function enabledRecordingButton(halt: boolean) {
  requestUsbButton.disabled = !halt;
  requestSerialButton.disabled = !halt;
}

export function setPopupCloseButton() {
  popupCloseButton.addEventListener('click', () => {
    overlay.classList.add('closed');
  });
}

export function closePopup() {
  overlay.classList.remove('closed');
}

export function addMessageToConsole(s: string) {
  messages.textContent += s;
  messages.scrollTo(0, messages.scrollHeight);
}

export function selectDutSerialAddClickEvent(fn: () => Promise<void>) {
  selectDutSerialButton.addEventListener('click', fn);
}

export function executeScriptAddClickEvent(fn: () => Promise<void>) {
  executeScriptButton.addEventListener('click', fn);
}

export function formAddSubmitEvent(fn: (e: Event) => Promise<void>) {
  dutCommandForm.addEventListener('submit', fn);
}

export function inputAddKeydownEvent(fn: (e: KeyboardEvent) => Promise<void>) {
  dutCommandInput.addEventListener('keydown', fn);
}

export function readInputValue() {
  const res = dutCommandInput.value;
  dutCommandInput.value = '';
  return res;
}

export function downloadAddClickEvent(fn: () => void) {
  downloadButton.addEventListener('click', fn);
}

export function analyzeAddClickEvent(fn: () => void) {
  analyzeButton.addEventListener('click', fn);
}

export function setDownloadAnchor(dataStr: string) {
  const dlAnchorElem = document.getElementById('downloadAnchorElem');
  if (dlAnchorElem === null) return;
  dlAnchorElem.setAttribute('href', dataStr);
  dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
  dlAnchorElem.click();
}

export function dropZoneAddDragoverEvent(fn: (evt: DragEvent) => void) {
  dropZone.addEventListener('dragover', fn, false);
}

export function dropZoneAddDropEvent(fn: (evt: DragEvent) => void) {
  dropZone.addEventListener('drop', fn, false);
}
