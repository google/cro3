import Dygraph from 'dygraphs';
import {Ui} from './ui';
import {AnnotationText, PowerData} from './power_test_controller';

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
  public updateGraph(powerData: Array<PowerData>) {
    if (powerData !== undefined && powerData.length > 0) {
      this.ui.hideToolTip();
    }
    this.g.updateOptions(
      {
        file: powerData,
        labels: ['t', 'ina0'],
        showRoller: true,
        xlabel: 'Relative Time (s)',
        ylabel: 'Power (mW)',
        legend: 'always',
        showRangeSelector: true,
        connectSeparatedPoints: true,
        axes: {
          x: {
            axisLabelFormatter: function (d) {
              const relativeTime = (d as number) - powerData[0][0];
              return (relativeTime / 1000).toLocaleString();
            },
          },
        },
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
      this.addAnnotation(
        powerData[powerData.length - 1][0],
        this.annotationText
      );
      this.annotationFlag = false;
    }
  }
  public setAnnotationFlag(text: AnnotationText) {
    this.annotationFlag = true;
    this.annotationText = text;
  }
  public addAnnotation(x: number, text: string) {
    function capitalize(str: string) {
      return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    }
    const capitalizedText = capitalize(text);
    const newAnnotation = {
      series: 'ina0',
      x: x,
      shortText: capitalizedText,
      text: capitalizedText,
      width: 36,
      cssClass: 'annotation',
    };
    this.annotations.push(newAnnotation);
    this.g.setAnnotations(this.annotations);
  }
  public findAnnotationPoint(
    powerData: Array<PowerData>,
    time: number,
    text: string
  ) {
    for (const powerDataElement of powerData) {
      if (time < powerDataElement[0]) {
        this.addAnnotation(powerDataElement[0], text);
        break;
      }
    }
  }
  public returnXrange() {
    console.log(this.g.xAxisExtremes());
    return this.g.xAxisRange();
  }
}
