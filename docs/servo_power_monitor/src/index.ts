// while true ; do { echo "do nothing for 5 sec" ; sleep 5 ; echo "yes for 5 sec
// without displaying" ; timeout 5 yes > /dev/null ; } ; done ectool
// chargecontrol idle ectool chargecontrol normal

import {analyzeData} from './analyzeData';
import {downloadJsonFile} from './downloadJsonFile';
import {dutSerialConsole} from './dutSerialConsole';
import {powerGraph} from './graph';
import {importJsonFile} from './importJsonFile';
import {powerMonitor} from './main';

window.addEventListener('DOMContentLoaded', () => {
  const graph = new powerGraph();
  const monitor = new powerMonitor(graph);
  const dut = new dutSerialConsole();
  const importFile = new importJsonFile(graph);
  const downloadFile = new downloadJsonFile(graph);
  const analyze = new analyzeData(graph);
  monitor.setupHtmlEvent();
  dut.setupHtmlEvent();
  importFile.setupHtmlEvent();
  downloadFile.setupHtmlEvent();
  analyze.setupHtmlEvent();
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
});
