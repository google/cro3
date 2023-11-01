const requestUsbButton = document.getElementById(
  'request-device'
) as HTMLButtonElement;
const requestSerialButton = document.getElementById(
  'requestSerialButton'
) as HTMLButtonElement;
const haltButton = document.getElementById('haltButton') as HTMLButtonElement;
const serial_output = document.getElementById(
  'serial_output'
) as HTMLDivElement;

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

export function addServoConsole(s: string) {
  serial_output.textContent = s;
}
