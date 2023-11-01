import {powerGraph} from './graph';

export class importJsonFile {
  graph: powerGraph;
  dropZone = document.getElementById('dropZone') as HTMLSpanElement;

  constructor(graph: powerGraph) {
    this.graph = graph;
  }
  handleFileSelect(evt: DragEvent) {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    const file = eventDataTransfer.files[0];
    if (file === undefined) {
      return;
    }
    const r = new FileReader();
    r.addEventListener('load', () => {
      const data = JSON.parse(r.result as string);
      this.graph.updateData(
        data.power.map((d: string) => [new Date(d[0]), d[1]])
      );
      this.graph.updateGraph();
    });
    r.readAsText(file);
  }
  handleDragOver(evt: DragEvent) {
    evt.stopPropagation();
    evt.preventDefault();
    const eventDataTransfer = evt.dataTransfer;
    if (eventDataTransfer === null) return;
    eventDataTransfer.dropEffect = 'copy'; // Explicitly show this is a copy.
  }
  setupHtmlEvent() {
    this.dropZone.addEventListener(
      'dragover',
      e => this.handleDragOver(e),
      false
    );
    this.dropZone.addEventListener(
      'drop',
      e => this.handleFileSelect(e),
      false
    );
  }
}
