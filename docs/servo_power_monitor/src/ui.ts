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
const serial_output = document.getElementById(
  'serial_output'
) as HTMLDivElement;
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

export function setPopupCloseButton() {}

export function addServoConsole(s: string) {
  serial_output.textContent = s;
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
