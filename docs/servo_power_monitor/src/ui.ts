import moment from 'moment';

const requestUSBButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const downloadButton = document.getElementById(
  'downloadButton'
) as HTMLButtonElement;
const selectDUTSerialButton = document.getElementById(
  'selectDUTSerialButton'
) as HTMLButtonElement;
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
const messages = document.getElementById('messages') as HTMLUListElement;
const executeScriptButton = document.getElementById(
  'executeScriptButton'
) as HTMLButtonElement;

export function requestSerialAddClickEvent(fn: () => Promise<void>) {
  requestSerialButton.addEventListener('click', fn);
}

export function requestUSBAddClickEvent(fn: () => Promise<void>) {
  requestUSBButton.addEventListener('click', fn);
}

export function useIsMeasuring(isMeasuring: boolean) {
  if (isMeasuring) {
    requestUSBButton.disabled = true;
    requestSerialButton.disabled = true;
  } else {
    requestUSBButton.disabled = false;
    requestSerialButton.disabled = false;
  }
}

export function setPopupCloseButton() {
  popupCloseButton.addEventListener('click', () => {
    overlay.classList.add('closed');
  });
}

export function closePopup() {
  overlay.classList.remove('closed');
}

export function addEmptyListItemToMessages() {
  const listItem = document.createElement('li');
  messages.appendChild(listItem);
  return listItem;
}

export function addMessageToConsole(listItem: HTMLLIElement, s: string) {
  listItem.textContent += s;
  messages.scrollTo(0, messages.scrollHeight);
}

export function executeScriptAddClickEvent(fn: () => Promise<void>) {
  executeScriptButton.addEventListener('click', fn);
}
export function selectDUTSerialAddClickEvent(fn: () => Promise<void>) {
  selectDUTSerialButton.addEventListener('click', fn);
}

export function downloadButtonAddClickEvent(fn: () => Promise<void>) {
  downloadButton.addEventListener('click', fn);
}

export function setDownloadAnchor(dataStr: string) {
  const dlAnchorElem = document.getElementById('downloadAnchorElem');
  if (dlAnchorElem === null) return;
  dlAnchorElem.setAttribute('href', dataStr);
  dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
  dlAnchorElem.click();
}
