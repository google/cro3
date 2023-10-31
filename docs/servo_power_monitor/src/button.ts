export class buttonElement {
  element: HTMLButtonElement;
  constructor(elementId: string) {
    this.element = document.getElementById(elementId) as HTMLButtonElement;
  }
  setDisabled = (disabledFlag: boolean) => {
    this.element.disabled = disabledFlag;
  };
  addEvent = (fn: () => Promise<void>) => {
    this.element.addEventListener('click', fn);
  };
}
export class divElement {
  element: HTMLDivElement;
  constructor(elementId: string) {
    this.element = document.getElementById(elementId) as HTMLDivElement;
  }
  addTextContent = (s: string) => {
    this.element.textContent += s;
    this.element.scrollTo(0, this.element.scrollHeight);
  };
  updateTextContent = (s: string) => {
    this.element.textContent = s;
  };
}
