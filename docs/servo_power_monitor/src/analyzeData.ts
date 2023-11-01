import {powerGraph} from './graph';
import {histogram} from './histogram';

export class analyzeData {
  graph: powerGraph;
  histogram = new histogram();
  analyzeButton = document.getElementById('analyzeButton') as HTMLButtonElement;
  constructor(graph: powerGraph) {
    this.graph = graph;
  }
  analyzePowerData() {
    // https://dygraphs.com/jsdoc/symbols/Dygraph.html#xAxisRange
    const xrange = this.graph.g.xAxisRange();
    console.log(this.graph.g.xAxisExtremes());
    const left = xrange[0];
    const right = xrange[1];
    this.histogram.paintHistogram(left, right, this.graph.powerData);
  }
  setupHtmlEvent() {
    this.analyzeButton.addEventListener('click', () => this.analyzePowerData());
  }
}
