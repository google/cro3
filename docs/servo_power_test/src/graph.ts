import Dygraph, {dygraphs} from 'dygraphs';
import {Ui} from './ui';
import {AnnotationDataList, PowerData} from './power_test_controller';
import * as d3 from 'd3';

export class Graph {
  private ui: Ui;
  private g: Dygraph;
  private histogramDiv: HTMLElement;
  public annotations: dygraphs.Annotation[] = [];
  constructor(ui: Ui, graphDiv: HTMLElement, histogramDiv: HTMLElement) {
    this.ui = ui;
    this.g = new Dygraph(graphDiv, [], {
      height: 500,
    });
    this.histogramDiv = histogramDiv;
  }
  public updateGraph(powerDataList: Array<PowerData>) {
    if (powerDataList !== undefined && powerDataList.length > 0) {
      this.ui.hideElement(this.ui.toolTip);
    }
    this.g.updateOptions(
      {
        file: powerDataList,
        labels: ['t', 'ina0'],
        showRoller: true,
        xlabel: 'Relative Time (s)',
        ylabel: 'Power (mW)',
        legend: 'always',
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
    annotationList: AnnotationDataList
  ) {
    annotationList.forEach((time: number, labelName: string) => {
      for (let i = powerDataList.length - 1; i >= 0; i--) {
        if (time > powerDataList[i][0]) {
          this.addAnnotation(powerDataList[i][0], labelName);
          break;
        }
      }
    });
  }
  public returnXrange() {
    console.log(this.g.xAxisExtremes());
    return this.g.xAxisRange();
  }
  public setHistogram(powerDataList: Array<PowerData>) {
    const parentElementSize = d3
      .select(this.histogramDiv)
      .node()
      ?.getBoundingClientRect();

    // set the dimensions and margins of the graph
    const margin = {top: 10, right: 30, bottom: 30, left: 40};
    const width = parentElementSize?.width;
    const height = parentElementSize?.height;

    // Bin the data.
    const bins = d3.bin().thresholds(40)(powerDataList.map(d => d[1]));
    console.log(bins);

    // Create the SVG container.
    const svg = d3
      .select(this.histogramDiv)
      .append('svg')
      .attr('width', width!)
      .attr('height', height!)
      .attr('viewBox', [0, 0, width!, height!]);

    // Declare the x (horizontal position) scale.
    const x = d3
      .scaleLinear()
      .domain([0, d3.max(bins, d => d.length)!])
      .range([margin.left, width! - margin.right]);

    // Declare the y (vertical position) scale.
    const y = d3
      .scaleLinear()
      .domain([bins[0].x0!, bins[bins.length - 1].x1!])
      .range([height! - margin.bottom, margin.top]);

    // Add a rect for each bin.
    svg
      .append('g')
      .attr('fill', 'steelblue')
      .selectAll()
      .data(bins)
      .join('rect')
      .attr('x', x(0))
      .attr('width', d => x(d.length) - x(0))
      .attr('y', d => y(d.x1!) + 1)
      .attr('height', d => y(d.x0!) - y(d.x1!) - 1);

    // Add the x-axis and label.
    svg
      .append('g')
      .attr('transform', `translate(0,${height! - margin.bottom})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(width! / 80)
          .tickSizeOuter(0)
      )
      .call(g =>
        g
          .append('text')
          .attr('x', width!)
          .attr('y', margin.bottom - 4)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'end')
          .text('# of datapoints')
      );

    // Add the y-axis and label, and remove the domain line.
    svg
      .append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(height! / 40))
      .call(g => g.select('.domain').remove())
      .call(g =>
        g
          .append('text')
          .attr('x', -margin.left)
          .attr('y', 10)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'start')
          .text('Power(mW)')
      );

    // Return the SVG element.
    svg.node();
  }
}
