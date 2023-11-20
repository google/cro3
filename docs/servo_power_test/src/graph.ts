import Dygraph, {dygraphs} from 'dygraphs';
import {Ui} from './ui';
import {AnnotationData, PowerData} from './power_test_controller';

export class Graph {
  private ui: Ui;
  private g: Dygraph;
  public annotations: dygraphs.Annotation[] = [];
  constructor(ui: Ui, div: HTMLElement) {
    this.ui = ui;
    this.g = new Dygraph(div, [], {
      width: 960,
      height: 480,
    });
  }
  public updateGraph(powerDataList: Array<PowerData>) {
    if (powerDataList !== undefined && powerDataList.length > 0) {
      this.ui.hideToolTip();
    }
    this.g.updateOptions(
      {
        file: powerDataList,
        labels: ['t', 'ina0'],
        showRoller: true,
        width: 960,
        height: 480,
        xlabel: 'Relative Time (s)',
        ylabel: 'Power (mW)',
        legend: 'always',
        showRangeSelector: true,
        connectSeparatedPoints: true,
        axes: {
          x: {
            axisLabelFormatter: function (d) {
              const relativeTime = (d as number) - powerDataList[0][0];
              // relativeTime is divided by 1000 because the time data is recorded in milliseconds but x-axis is in seconds.
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
    powerDataList: Array<PowerData>,
    annotationList: Array<AnnotationData>
  ) {
    for (const ann of annotationList) {
      for (let i = powerDataList.length - 1; i >= 0; i--) {
        if (ann[0] > powerDataList[i][0]) {
          this.addAnnotation(powerDataList[i][0], ann[1]);
          break;
        }
      }
    }
  }
  public returnXrange() {
    console.log(this.g.xAxisExtremes());
    return this.g.xAxisRange();
  }
}
