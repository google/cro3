import moment from 'moment';
const popupCloseButton = document.getElementById(
  'popup-close'
) as HTMLButtonElement;
const overlay = document.querySelector('#popup-overlay') as HTMLDivElement;

export function setPopupCloseButton() {
  popupCloseButton.addEventListener('click', () => {
    overlay.classList.add('closed');
  });
}

export function closePopup() {
  overlay.classList.remove('closed');
}

export function setDownloadAnchor(dataStr: string) {
  const dlAnchorElem = document.getElementById('downloadAnchorElem');
  if (dlAnchorElem === null) return;
  dlAnchorElem.setAttribute('href', dataStr);
  dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
  dlAnchorElem.click();
}
