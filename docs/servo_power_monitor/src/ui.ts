const downloadButton = document.getElementById(
  'downloadButton'
) as HTMLButtonElement;
const requestUSBButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const serial_output = document.getElementById(
  'serial_output'
) as HTMLDivElement;
const controlDiv = document.getElementById('controlDiv') as HTMLDivElement;
const selectDUTSerialButton = document.getElementById(
  'selectDUTSerialButton'
) as HTMLButtonElement;
const executeScriptButton = document.getElementById(
  'executeScriptButton'
) as HTMLButtonElement;
const messages = document.getElementById('messages') as HTMLUListElement;
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;
const form = document.getElementById('form') as HTMLFormElement;

export function addEventSelectDUTSerial(Fn: () => Promise<void>) {
  selectDUTSerialButton.addEventListener('click', Fn);
}

export function toggleSerialButton() {
  requestSerialButton.disabled = !requestSerialButton.disabled;
}

export function addEventSerial(Fn: () => void) {
  requestSerialButton.addEventListener('click', Fn);
}

export function addListItem(s: string) {
  const listItem = document.createElement('li');
  messages.appendChild(listItem);
  listItem.textContent = s;
}

export function addEventForm(Fn: () => Promise<void>) {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    await Fn();
  });
}
