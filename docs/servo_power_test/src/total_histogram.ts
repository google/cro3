import * as d3 from 'd3';
import {PowerData} from './power_test_controller';

export class TotalHistogram {
  private colorPalette = [
    'rgba(66, 133, 244, 0.7)', // #4285f4
    'rgba(234, 67, 53, 0.7)', // #ea4335
    'rgba(251, 188, 4, 0.7)', // #fbbc04
    'rgba(52, 168, 83, 0.7)', // #34a853
    'rgba(250, 123, 23, 0.7)', // #fa7b17
    'rgba(245, 56, 160, 0.7)', // #f538a0
    'rgba(161, 66, 244, 0.7)', // #a142f4
    'rgba(36, 193, 224, 0.7)', // #24c1e0
  ];
  public paintHistogram(totalPowerDataList: Array<Array<PowerData>>) {
    // Declare the chart dimensions and margins.
    const margin = {top: 10, bottom: 30, right: 40, left: 40};
    const width = 960;
    const height = 320;

    // Bin the data.
    const binsList: Array<Array<d3.Bin<number, number>>> = [];
    let minValue = 1000000;
    let maxValue = 0;
    let maxNum = 0;
    for (const powerDataList of totalPowerDataList) {
      const bins = d3.bin().thresholds(40)(powerDataList.map(d => d[1]));
      binsList.push(bins);
      minValue = d3.min([minValue, bins[0].x0!])!;
      maxValue = d3.max([maxValue, bins[bins.length - 1].x1!])!;
      maxNum = d3.max([maxNum, d3.max(bins, d => d.length)!])!;
    }

    // Declare the x (horizontal position) scale.
    const x = d3
      .scaleLinear()
      .domain([minValue, maxValue])
      .range([margin.left, width - margin.right]);

    // Declare the y (vertical position) scale.
    const y = d3
      .scaleLinear()
      .domain([0, maxNum])
      .range([height - margin.bottom, margin.top]);

    // Create the SVG container.
    const svg = d3
      .select('#total-histogram')
      .append('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .attr('style', 'max-width: 100%; height: auto;');

    // Add a rect for each bin.
    for (let i = 0; i < binsList.length; i++) {
      const color = this.colorPalette[i % this.colorPalette.length];
      svg
        .append('g')
        .attr('fill', color)
        .selectAll()
        .data(binsList[i])
        .join('rect')
        .attr('x', d => x(d.x0!) + 1)
        .attr('width', d => x(d.x1!) - x(d.x0!) - 1)
        .attr('y', d => y(d.length))
        .attr('height', d => y(0) - y(d.length));
      svg
        .append('circle')
        .attr('cx', width - margin.right - 100)
        .attr('cy', margin.top + 20 * i)
        .attr('r', 6)
        .style('fill', color);
      svg
        .append('text')
        .attr('x', width - margin.right - 90)
        .attr('y', margin.top + 20 * i)
        .attr('fill', 'currentColor')
        .text(`config ${i + 1}`)
        .style('font-size', '12px')
        .attr('alignment-baseline', 'middle');
    }

    // Add the x-axis and label.
    svg
      .append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(width / 80)
          .tickSizeOuter(0)
      )
      .call(g =>
        g
          .append('text')
          .attr('x', width)
          .attr('y', margin.bottom - 4)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'end')
          .text('Power (mW)')
      );

    // Add the y-axis and label, and remove the domain line.
    svg
      .append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(height / 40))
      .call(g => g.select('.domain').remove())
      .call(g =>
        g
          .append('text')
          .attr('x', -margin.left)
          .attr('y', 10)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'start')
          .text('# of datapoints')
      );

    // Return the SVG element.
    svg.node();
  }
}
