import * as d3 from 'd3';

export class TotalHistogram {
  private colorPalette = [
    '#4285f4',
    '#ea4335',
    '#fbbc04',
    '#34a853',
    '#fa7b17',
    '#f538a0',
    '#a142f4',
    '#24c1e0',
  ];
  public paintHistogram(totalPowerDataList: Array<Array<number>>) {
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
      minValue = Math.min(minValue, Math.min(...powerDataList));
      maxValue = Math.max(maxValue, Math.max(...powerDataList));
    }

    // Declare the x (horizontal position) scale.
    const x = d3
      .scaleLinear()
      .domain([minValue, maxValue])
      .range([margin.left, width - margin.right]);

    const histogram = d3
      .bin()
      .domain([minValue, maxValue]) // then the domain of the graphic
      .thresholds(x.ticks(40)); // then the numbers of bins

    for (const powerDataList of totalPowerDataList) {
      const bins = histogram(powerDataList);
      binsList.push(bins);
      maxNum = d3.max([maxNum, d3.max(bins, d => d.length)!])!;
    }

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
        .append('path')
        .datum(
          binsList[i].map(e => {
            return [(e.x0! + e.x1!) / 2, e.length] as [number, number];
          })
        )
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 1)
        .attr(
          'd',
          d3
            .line()
            .x(d => x(d[0]))
            .y(d => y(d[1]))
        );
      svg
        .selectAll('dataCircle')
        .data(binsList[i])
        .enter()
        .append('circle')
        .attr('fill', color)
        .attr('stroke', 'none')
        .attr('cx', d => x((d.x0! + d.x1!) / 2))
        .attr('cy', d => y(d.length))
        .attr('r', 3);
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
          .attr('x', width - margin.right)
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
          .attr('x', 5)
          .attr('y', margin.top)
          .attr('fill', 'currentColor')
          .attr('text-anchor', 'start')
          .text('# of datapoints')
      );

    // Return the SVG element.
    svg.node();
  }
}
