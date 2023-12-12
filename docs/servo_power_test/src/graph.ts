import Dygraph, {dygraphs} from 'dygraphs';
import {Ui} from './ui';
import {AnnotationDataList, PowerData} from './power_test_controller';
import * as d3 from 'd3';

export class Graph {
  private ui: Ui;
  private g: Dygraph;
  private startExtractTime: number;
  private endExtractTime: number;
  public annotations: dygraphs.Annotation[] = [];
  private margin = {top: 10, right: 30, bottom: 30, left: 40};
  private histogramInfo;
  constructor(ui: Ui, graphDiv: HTMLElement, histogramDiv: HTMLElement) {
    this.ui = ui;
    this.g = new Dygraph(graphDiv, [], {
      height: 480,
    });
    this.startExtractTime = 0;
    this.endExtractTime = 0;
    const parentElementSize = d3
      .select(histogramDiv)
      .node()
      ?.getBoundingClientRect();
    this.histogramInfo = {
      width: parentElementSize!.width!,
      height: parentElementSize!.height!,
      svg: d3
        .select(histogramDiv)
        .append('svg')
        .attr('width', parentElementSize!.width!)
        .attr('height', parentElementSize!.height!)
        .attr('viewBox', [
          0,
          0,
          parentElementSize!.width!,
          parentElementSize!.height!,
        ]),
      x: d3.scaleLinear(),
      y: d3.scaleLinear(),
    };
  }
  public setExtractTime(startExtractTime: number, endExtractTime: number) {
    this.startExtractTime = startExtractTime;
    this.endExtractTime = endExtractTime;
  }
  public updateGraph(powerDataList: Array<PowerData>, powerAverage: number) {
    if (powerDataList !== undefined && powerDataList.length > 0) {
      this.ui.hideElement(this.ui.toolTip);
    }

    this.g.updateOptions(
      {
        file: powerDataList,
        labels: ['t', 'ina0'],
        showRoller: true,
        height: 480,
        xlabel: 'Relative Time (s)',
        ylabel: 'Power (mW)',
        legend: 'always',
        connectSeparatedPoints: true,
        strokeWidth: 2,
        axes: {
          x: {
            axisLabelFormatter: function (d) {
              const relativeTime = (d as number) - powerDataList[0][0];
              // relativeTime is divided by 1000 because the time data is recorded in milliseconds but x-axis is in seconds.
              return (relativeTime / 1000).toLocaleString();
            },
          },
        },
        underlayCallback: (canvas, area, g) => {
          function highlightPeriod(x_start: number, x_end: number) {
            if (x_start === 0 || x_end === 0) return;
            const canvas_left_x = g.toDomXCoord(x_start);
            const canvas_right_x = g.toDomXCoord(x_end);
            const canvas_width = canvas_right_x - canvas_left_x;
            canvas.fillStyle = 'rgba(255, 255, 0, 0.5)';
            canvas.fillRect(canvas_left_x, area.y, canvas_width, area.h);
          }
          function drawHorizontalLine(yValue: number) {
            const canvas_y = g.toDomYCoord(yValue);
            canvas.fillStyle = '#FF4500';
            canvas.strokeStyle = '#FF4500';
            canvas.beginPath();
            canvas.moveTo(area.x, canvas_y);
            canvas.lineTo(area.x + area.w, canvas_y);
            canvas.stroke();
            canvas.font = '14px sans-serif';
            canvas.fillText('Average', area.x, canvas_y - 10);
          }
          highlightPeriod(this.startExtractTime, this.endExtractTime);
          if (powerAverage !== 0) drawHorizontalLine(powerAverage);
          drawHorizontalLine(powerAverage);
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
    return this.g.xAxisRange();
  }
  public clearHistogram() {
    this.histogramInfo.svg.selectAll('g').remove();
  }
  public updateHistogramAxis(histogramDataList: Array<number>) {
    // Bin the data.
    const bins = d3
      .bin()
      .thresholds((data, min, max) => d3.range(min!, max!, 100))(
      histogramDataList
    );

    // Declare the x (horizontal position) scale.
    this.histogramInfo.x
      .domain([0, d3.max(bins, d => d.length)!])
      .range([this.margin.left, this.histogramInfo.width - this.margin.right]);

    // Declare the y (vertical position) scale.
    this.histogramInfo.y
      .domain([bins[0].x0!, bins[bins.length - 1].x1!])
      .range([
        this.histogramInfo.height - this.margin.bottom,
        this.margin.top + 20,
      ]);

    // Add the x-axis and label.
    this.histogramInfo.svg
      .append('g')
      .attr(
        'transform',
        `translate(0,${this.histogramInfo.height - this.margin.bottom})`
      )
      .call(
        d3
          .axisBottom(this.histogramInfo.x)
          .ticks(this.histogramInfo.width! / 80)
          .tickSizeOuter(0)
      )
      .call(g =>
        g
          .append('text')
          .attr('x', this.histogramInfo.width)
          .attr('y', this.margin.bottom)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'end')
          .style('font-size', '12px')
          .text('# of datapoints')
      );

    // Add the y-axis and label, and remove the domain line.
    this.histogramInfo.svg
      .append('g')
      .attr('transform', `translate(${this.margin.left},0)`)
      .call(
        d3
          .axisLeft(this.histogramInfo.y)
          .ticks(this.histogramInfo.height / bins.length)
      )
      .call(g => g.select('.domain').remove())
      .call(g =>
        g
          .append('text')
          .attr('x', -32)
          .attr('y', 20)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'start')
          .style('font-size', '12px')
          .text('Power(mW)')
      );

    return bins;
  }
  // Draw a histogram with the data during workload running (that is, between 'start' and 'end' annotations).
  public updateHistogram(histogramDataList: Array<number>) {
    this.clearHistogram();
    const bins = this.updateHistogramAxis(histogramDataList);

    // Add a rect for each bin.
    this.histogramInfo.svg
      .append('g')
      .attr('fill', 'steelblue')
      .selectAll()
      .enter()
      .data(bins)
      .join('rect')
      .attr('stroke-width', 1)
      .attr('stroke', 'black')
      .attr('x', this.histogramInfo.x(0))
      .attr(
        'width',
        d => this.histogramInfo.x(d.length) - this.histogramInfo.x(0)
      )
      .attr('y', d => this.histogramInfo.y(d.x1!))
      .attr(
        'height',
        d => this.histogramInfo.y(d.x0!) - this.histogramInfo.y(d.x1!)
      );
  }
}
