// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {
  analyzePowerData,
  handleFileSelect,
  handleDragOver,
  executeScript,
  formSubmit,
  selectDutSerial,
  requestSerial,
  disconnectSerialPort,
  downloadJSONFile,
  stopMeasurement,
  cancelSubmit,
} from './main';
import {
  analyzeAddClickEvent,
  downloadAddClickEvent,
  dropZoneAddDragoverEvent,
  dropZoneAddDropEvent,
  executeScriptAddClickEvent,
  formAddSubmitEvent,
  haltAddClickEvent,
  inputAddKeydownEvent,
  requestSerialAddClickEvent,
  selectDutSerialAddClickEvent,
  setPopupCloseButton,
} from './ui';

window.addEventListener('DOMContentLoaded', () => {
  setPopupCloseButton();
  selectDutSerialAddClickEvent(selectDutSerial);
  formAddSubmitEvent(async e => formSubmit(e));
  inputAddKeydownEvent(async e => cancelSubmit(e));
  executeScriptAddClickEvent(executeScript);
  requestSerialAddClickEvent(requestSerial);
  // event when you disconnect serial port
  navigator.serial.addEventListener('disconnect', disconnectSerialPort);
  downloadAddClickEvent(downloadJSONFile);
  haltAddClickEvent(stopMeasurement);
  analyzeAddClickEvent(analyzePowerData);
  dropZoneAddDragoverEvent(handleDragOver);
  dropZoneAddDropEvent(handleFileSelect);
});
