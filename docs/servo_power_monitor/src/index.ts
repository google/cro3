// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {dutSerialConsole} from './dutSerialConsole';
import {powerGraph} from './graph';
import {importJsonFile} from './importJsonFile';
import {powerMonitor} from './main';
import {
  analyzeAddClickEvent,
  downloadAddClickEvent,
  haltAddClickEvent,
  requestSerialAddClickEvent,
  requestUsbAddClickEvent,
} from './ui';

window.addEventListener('DOMContentLoaded', () => {
  const graph = new powerGraph();
  const monitor = new powerMonitor(graph);
  const dut = new dutSerialConsole();
  const importFile = new importJsonFile(graph);
  dut.setupHtmlEvent();
  importFile.setupHtmlEvent();
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
});
