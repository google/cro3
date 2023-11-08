import Dygraph from 'dygraphs';
import {Ui} from './ui';
import {PowerDataType} from './power_test_controller';

type AnnotationText = 'start' | 'end';

export class Graph {
  private ui: Ui;
  public g = new Dygraph('graph', [], {});
  public annotations;
  public annotationFlag = false;
  private annotationText: AnnotationText = 'start';
  constructor(ui: Ui) {
    this.ui = ui;
    this.annotations = this.g.annotations();
  }
  public updateGraph(powerData: Array<PowerDataType>) {
    if (powerData !== undefined && powerData.length > 0) {
      this.ui.hideToolTip();
    }
    // currentData = data;
    this.g.updateOptions(
      {
        file: powerData,
        labels: ['t', 'ina0'],
        showRoller: true,
        ylabel: 'Power (mW)',
        legend: 'always',
        showRangeSelector: true,
        connectSeparatedPoints: true,
        underlayCallback: function (canvas, area, g) {
          canvas.fillStyle = 'rgba(255, 255, 102, 1.0)';

          function highlight_period(x_start: number, x_end: number) {
            const canvas_left_x = g.toDomXCoord(x_start);
            const canvas_right_x = g.toDomXCoord(x_end);
            const canvas_width = canvas_right_x - canvas_left_x;
            canvas.fillRect(canvas_left_x, area.y, canvas_width, area.h);
          }
          highlight_period(10, 10);
        },
      },
      false
    );
    if (this.annotationFlag) {
      this.addAnnotation(powerData[powerData.length - 1][0]);
      this.annotationFlag = false;
    }
  }
  public setAnnotationFlag(text: AnnotationText) {
    this.annotationFlag = true;
    this.annotationText = text;
  }
  private addAnnotation(x: Date) {
    const newAnnotation = {
      series: 'ina0',
      x: x.getTime(),
      shortText: this.annotationText === 'start' ? 'S' : 'E',
      text: this.annotationText,
    };
    this.annotations.push(newAnnotation);
    this.g.setAnnotations(this.annotations);
  }
  public updateAnnotation(annotations: Array<number|string>) {
    this.annotations = annotations.map(d => {
      series: 'ina0',
      x: d[0],
      shortText: d[1] === 'start' ? 'S' : 'E',
      text: d[1],
    });
    this.g.setAnnotations(this.annotations);
  }
  public returnXrange() {
    console.log(this.g.xAxisExtremes());
    return this.g.xAxisRange();
  }
}
