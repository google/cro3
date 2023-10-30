export declare function requestSerialAddClickEvent(
  fn: () => Promise<void>
): void;
export declare function requestUSBAddClickEvent(fn: () => Promise<void>): void;
export declare function haltAddClickEvent(fn: () => Promise<void>): void;
export declare function enabledRecordingButton(halt: boolean): void;
export declare function setPopupCloseButton(): void;
export declare function closePopup(): void;
export declare function addEmptyListItemToMessages(): void;
export declare function addMessageToConsole(s: string): void;
export declare function selectDUTSerialAddClickEvent(
  fn: () => Promise<void>
): void;
export declare function executeScriptAddClickEvent(
  fn: () => Promise<void>
): void;
export declare function formAddSubmitEvent(
  fn: (e: Event) => Promise<void>
): void;
export declare function inputAddKeydownEvent(
  fn: (e: KeyboardEvent) => Promise<void>
): void;
export declare function readInputValue(): string;
export declare function downloadAddClickEvent(fn: () => void): void;
export declare function analyzeAddClickEvent(fn: () => void): void;
export declare function setDownloadAnchor(dataStr: string): void;
export declare function dropZoneAddDragoverEvent(
  fn: (evt: DragEvent) => void
): void;
export declare function dropZoneAddDropEvent(
  fn: (evt: DragEvent) => void
): void;
