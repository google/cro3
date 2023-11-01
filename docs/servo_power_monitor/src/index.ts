// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {dutSerialConsole} from './dutSerialConsole';
import {powerMonitor} from './main';
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
  requestUsbAddClickEvent,
  selectDutSerialAddClickEvent,
  setPopupCloseButton,
} from './ui';

window.addEventListener('DOMContentLoaded', () => {
  const monitor = new powerMonitor();
  const dut = new dutSerialConsole();
  setPopupCloseButton();
  selectDutSerialAddClickEvent(() => dut.selectPort());
  formAddSubmitEvent(e => dut.formSubmit(e));
  inputAddKeydownEvent(e => dut.cancelSubmit(e));
  executeScriptAddClickEvent(() => dut.executeScript());
  requestUsbAddClickEvent(() => monitor.requestUsb());
  requestSerialAddClickEvent(() => monitor.requestSerial());
  // `disconnect` event is fired when a Usb device is disconnected.
  // c.f. https://wicg.github.io/webusb/#disconnect (5.1. Events)
  navigator.usb.addEventListener('disconnect', () =>
    monitor.disconnectUsbPort()
  );
  // event when you disconnect serial port
  navigator.serial.addEventListener('disconnect', () => {
    monitor.disconnectSerialPort();
    dut.disconnectPort();
  });
  downloadAddClickEvent(() => monitor.downloadJSONFile());
  haltAddClickEvent(() => monitor.stopMeasurement());
  analyzeAddClickEvent(() => monitor.analyzePowerData());
  dropZoneAddDragoverEvent(e => monitor.handleDragOver(e));
  dropZoneAddDropEvent(e => monitor.handleFileSelect(e));
});
