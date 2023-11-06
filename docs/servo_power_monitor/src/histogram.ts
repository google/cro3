import * as d3 from 'd3';
import moment from 'moment';

export class Histogram {
  ranges: Array<Array<number>> = [];
  paintHistogram(
    t0: number,
    t1: number,
    powerData: Array<Array<Date | number>>
  ) {
    // constants
    const xtick = 40;
    const boxWidth = 10;

    // setup a graph (drop if exists)
    const margin = {top: 60, right: 200, bottom: 0, left: 200};
    const area = d3.select('#d3area');
    const targetWidth =
      (area.node() as HTMLElement).getBoundingClientRect().width * 0.98;
    const targetHeight = 10000; // (area.node() as HTMLElement).getBoundingClientRect().height;
    const width = targetWidth - margin.left - margin.right;
    const svg = area
      .html('')
      .append('svg')
      .attr('height', targetHeight)
      .attr('width', targetWidth)
      .append('g')
      .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    // y axis and its label
    const dataAll: Array<number> = powerData.map(
      (e: Array<Date | number>) => e[1] as number
    );
    const dataMin = d3.min(dataAll);
    const dataMax = d3.max(dataAll);
    if (dataMin === undefined || dataMax === undefined) return;
    const ymin = dataMin - 1000;
    const ymax = dataMax + 1000;
    const y = d3.scaleLinear().domain([ymin, ymax]).range([0, width]);
    svg.append('g').call(d3.axisTop(y));
    svg
      .append('text')
      .attr('text-anchor', 'end')
      .attr('x', width)
      .attr('y', -margin.top / 2)
      .attr('stroke', '#fff')
      .text('Power (mW)');

    this.ranges.push([t0, t1]);

    for (let i = 0; i < this.ranges.length; i++) {
      // compute data and place of i-th series
      const left = this.ranges[i][0];
      const right = this.ranges[i][1];
      const points = powerData.filter(
        (e: Array<Date | number>) =>
          typeof e[0] !== 'number' &&
          left <= e[0].getTime() &&
          e[0].getTime() <= right
      );

      const data: Array<number> = points.map(
        (e: Array<Date | number>) => e[1] as number
      );
      const center = xtick * (i + 1);

      // Compute statistics
      const data_sorted = data.sort(d3.ascending);
      const q1 = d3.quantile(data_sorted, 0.25);
      const median = d3.quantile(data_sorted, 0.5);
      const q3 = d3.quantile(data_sorted, 0.75);
      if (q1 === undefined || q3 === undefined) return;
      if (median === undefined) return;
      const interQuantileRange = q3 - q1;
      const lowerFence = q1 - 1.5 * interQuantileRange;
      const upperFence = q3 + 1.5 * interQuantileRange;
      const minValue = d3.min(data);
      const maxValue = d3.max(data);
      const mean = d3.mean(data);
      if (
        minValue === undefined ||
        maxValue === undefined ||
        mean === undefined
      )
        return;

      // min, mean, max
      svg
        .append('line')
        .attr('y1', center)
        .attr('y2', center)
        .attr('x1', y(minValue))
        .attr('x2', y(maxValue))
        .style('stroke-dasharray', '3, 3')
        .attr('stroke', '#aaa');
      svg
        .selectAll('toto')
        .data([minValue, mean, maxValue])
        .enter()
        .append('line')
        .attr('y1', center - boxWidth)
        .attr('y2', center + boxWidth)
        .attr('x1', d => {
          return y(d);
        })
        .attr('x2', d => {
          return y(d);
        })
        .style('stroke-dasharray', '3, 3')
        .attr('stroke', '#aaa');

      // box and line
      svg
        .append('line')
        .attr('y1', center)
        .attr('y2', center)
        .attr('x1', y(lowerFence))
        .attr('x2', y(upperFence))
        .attr('stroke', '#fff');
      svg
        .append('rect')
        .attr('y', center - boxWidth / 2)
        .attr('x', y(q1))
        .attr('width', y(q3) - y(q1))
        .attr('height', boxWidth)
        .attr('stroke', '#fff')
        .style('fill', '#69b3a2');
      svg
        .selectAll('toto')
        .data([lowerFence, median, upperFence])
        .enter()
        .append('line')
        .attr('y1', center - boxWidth / 2)
        .attr('y2', center + boxWidth / 2)
        .attr('x1', d => {
          return y(d);
        })
        .attr('x2', d => {
          return y(d);
        })
        .attr('stroke', '#fff');

      svg
        .append('text')
        .attr('text-anchor', 'end')
        .attr('alignment-baseline', 'baseline')
        .attr('y', center - boxWidth / 4)
        .attr('x', 0)
        .attr('font-size', boxWidth)
        .attr('stroke', '#fff')
        .text(`${moment(left).format()}`);
      svg
        .append('text')
        .attr('text-anchor', 'end')
        .attr('alignment-baseline', 'hanging')
        .attr('y', center + boxWidth / 4)
        .attr('x', 0)
        .attr('font-size', boxWidth)
        .attr('stroke', '#fff')
        .text(`${moment(right).format()}`);

      svg
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('alignment-baseline', 'baseline')
        .attr('y', center - boxWidth)
        .attr('x', y(mean))
        .attr('font-size', boxWidth)
        .attr('stroke', '#fff')
        .text(`mean:${mean | 0}`);

      svg
        .append('text')
        .attr('text-anchor', 'middle')
        .attr('alignment-baseline', 'hanging')
        .attr('y', center + boxWidth)
        .attr('x', y(median))
        .attr('font-size', boxWidth)
        .attr('stroke', '#fff')
        .text(`median:${median}`);

      svg
        .append('text')
        .attr('text-anchor', 'start')
        .attr('alignment-baseline', 'hanging')
        .attr('y', center + boxWidth)
        .attr('x', y(ymax))
        .attr('font-size', boxWidth)
        .attr('stroke', '#fff')
        .text(`N:${data.length}`);
    }
  }
}
