import moment from 'moment';

const requestUSBButton = document.getElementById(
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
const selectDUTSerialButton = document.getElementById(
  'selectDUTSerialButton'
) as HTMLButtonElement;
const form = document.getElementById('form') as HTMLFormElement;
const input = document.getElementById('input') as HTMLInputElement;
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
const messages = document.getElementById('messages') as HTMLUListElement;
const executeScriptButton = document.getElementById(
  'executeScriptButton'
) as HTMLButtonElement;
const dropZone = document.getElementById('dropZone') as HTMLSpanElement;

export function requestSerialAddClickEvent(fn: () => Promise<void>) {
  requestSerialButton.addEventListener('click', fn);
}

export function requestUSBAddClickEvent(fn: () => Promise<void>) {
  requestUSBButton.addEventListener('click', fn);
}

export function haltAddClickEvent(fn: () => Promise<void>) {
  haltButton.addEventListener('click', fn);
}

export function enabledRecordingButton(halt: boolean) {
  requestUSBButton.disabled = !halt;
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

let listItem: HTMLLIElement;

export function addEmptyListItemToMessages() {
  listItem = document.createElement('li');
  messages.appendChild(listItem);
}

export function addMessageToConsole(s: string) {
  listItem.textContent += s;
  messages.scrollTo(0, messages.scrollHeight);
}

export function selectDUTSerialAddClickEvent(fn: () => Promise<void>) {
  selectDUTSerialButton.addEventListener('click', fn);
}

export function executeScriptAddClickEvent(fn: () => Promise<void>) {
  executeScriptButton.addEventListener('click', fn);
}

export function formAddSubmitEvent(fn: (e: Event) => Promise<void>) {
  form.addEventListener('submit', fn);
}

export function readInputValue() {
  const res = input.value;
  input.value = '';
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
