import {powerGraph} from './graph';
import moment from 'moment';

export class downloadJsonFile {
  graph: powerGraph;
  downloadButton = document.getElementById(
    'downloadButton'
  ) as HTMLButtonElement;
  constructor(graph: powerGraph) {
    this.graph = graph;
  }
  setDownloadAnchor(dataStr: string) {
    const dlAnchorElem = document.getElementById('downloadAnchorElem');
    if (dlAnchorElem === null) return;
    dlAnchorElem.setAttribute('href', dataStr);
    dlAnchorElem.setAttribute('download', `power_${moment().format()}.json`);
    dlAnchorElem.click();
  }
  downloadJSONFile() {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(JSON.stringify({power: this.graph.powerData}));
    this.setDownloadAnchor(dataStr);
  }
  setupHtmlEvent() {
    this.downloadButton.addEventListener('click', () =>
      this.downloadJSONFile()
    );
  }
}
