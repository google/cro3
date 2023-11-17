import * as d3 from 'd3';
import {PowerData} from './power_test_controller';

export class TotalHistogram {
  public paintHistogram(powerDataList: Array<PowerData>) {
    // Declare the chart dimensions and margins.
    const margin = {top: 10, bottom: 10, right: 10, left: 10};
    const width = 960;
    const height = 500;

    // Bin the data.
    const bins = d3
      .bin()
      .thresholds(40)
      .value(d => d[0])(powerDataList);

    // Declare the x (horizontal position) scale.
    const x = d3
      .scaleLinear()
      .domain([bins[0].x0!, bins[bins.length - 1].x1!])
      .range([margin.left, width - margin.right]);

    // Declare the y (vertical position) scale.
    const y = d3
      .scaleLinear()
      .domain([0, d3.max(bins, d => d.length)!])
      .range([height - margin.bottom, margin.top]);

    // Create the SVG container.
    const svg = d3
      .create('svg')
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height])
      .attr('style', 'max-width: 100%; height: auto;');

    // Add a rect for each bin.
    svg
      .append('g')
      .attr('fill', 'steelblue')
      .selectAll()
      .data(bins)
      .join('rect')
      .attr('x', d => x(d.x0!) + 1)
      .attr('width', d => x(d.x1!) - x(d.x0!) - 1)
      .attr('y', d => y(d.length))
      .attr('height', d => y(0) - y(d.length));

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
          .text('Unemployment rate (%) →')
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
          .text('↑ Frequency (no. of counties)')
      );

    // Return the SVG element.
    svg.node();
  }
}
