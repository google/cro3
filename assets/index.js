const colorPalette = [
  '#e60049', '#0bb4ff', '#50e991', '#e6d800', '#9b19f5', '#ffa300', '#dc0ab4',
  '#b3d4ff', '#00bfa0', '#ea5545', '#bdcf32', '#b30000', '#7c1158', '#4421af',
  '#1a53ff', '#0d88e6', '#00b7c7', '#5ad45a', '#8be04e', '#ebdc78',
];

function setSeriesColor(g, name, color) {
  const option = {};
  option.series = {};
  option.series[name] = {color: color};
  g.updateOptions(option)

  const key = btoa(name);
  const labelNode = document.getElementById(`filter_${key}`);
  labelNode.style.color = color;
}

function setSeriesLabelVisibility(g, name, isVisible) {
  // isVisible === true => make it visible
  // isVisible === false => make it invisible
  // isVisible === null => keep the current state
  if (isVisible === null) {
    return;
  }
  const key = btoa(name);
  const labelNode = document.getElementById(`filter_${key}`);
  if (isVisible) {
    const props = g.getPropertiesForSeries(name);
    labelNode.style.color = props.color;
  } else {
    labelNode.style.color = '#c0c0c0';
  }
}

function setSeriesVisibilityWithPredicate(g, f) {
  const visibilityList = g.visibility();
  const labels = g.getLabels().splice(1);
  for (const i in labels) {
    const name = labels[i];
    const v = f(name);
    if (v !== null) {
      visibilityList[i] = v;
      setSeriesLabelVisibility(g, name, v);
    }
  }
  g.setVisibility(visibilityList);
}


function createFilterLabels(name) {
  const row = document.createElement('div');
  const key = btoa(name);
  row.innerHTML = `<span class="toggleLabel" id="filter_${key}">${name}</span>`;
  return row;
}

function updateFilterDiv(g) {
  const labels = g.getLabels().splice(1);

  const hwidDict = {};
  const serialDict = {};
  for (const labelIndex in labels) {
    const label = labels[labelIndex];
    const labelElements = label.split('/');

    const hwid = labelElements[0];
    if (hwidDict[hwid] === undefined) {
      hwidDict[hwid] = {};
    }
    hwidDict[hwid][label] = true;

    const serial = labelElements[1];
    if (serialDict[serial] === undefined) {
      serialDict[serial] = {};
    }
    serialDict[serial][label] = true;
  }

  const filterDiv = document.getElementById('filterDiv');
  filterDiv.innerHTML = '';
  window.filterDiv = filterDiv;

  {
    const header = document.createElement('h2');
    header.text = 'Series';
    filterDiv.appendChild(header);
  }

  for (const labelIndex in labels) {
    const label = labels[labelIndex];
    const labelNode = createFilterLabels(label);
    const props = g.getPropertiesForSeries(label);
    labelNode.style.color = props.color;
    filterDiv.appendChild(labelNode);
  }

  {
    const header = document.createElement('h2');
    header.text = 'HWID';
    filterDiv.appendChild(header);
  }
  for (const hwid in hwidDict) {
    const row = filterDiv.appendChild(document.createElement('div'));
    const key = btoa(hwid);
    {
      const showButton = row.appendChild(document.createElement('button'));
      showButton.innerText = 'Show';
      showButton.addEventListener('click', function() {
        console.log(`show ${hwid}`);
        for (g of window.charts) {
          setSeriesVisibilityWithPredicate(g, (name) => {
            return hwidDict[hwid][name] ? true : null;
          });
        }
      });
    }
    {
      const hideButton = row.appendChild(document.createElement('button'));
      hideButton.innerText = 'Hide';
      hideButton.addEventListener('click', function() {
        console.log(`hide ${hwid}`);
        setSeriesVisibilityWithPredicate(g, (name) => {
          return hwidDict[hwid][name] ? false : null;
        });
      });
    }
    {
      const showOnlyButton = row.appendChild(document.createElement('button'));
      showOnlyButton.innerText = 'Only';
      showOnlyButton.addEventListener('click', function() {
        console.log(`only ${hwid}`);
        setSeriesVisibilityWithPredicate(g, (name) => {
          return hwidDict[hwid][name] ? true : false;
        });
      });
    }
    row.appendChild(document.createTextNode(hwid));
  }

  {
    const header = document.createElement('h2');
    header.text = 'DUT';
    filterDiv.appendChild(header);
  }
  for (const serial in serialDict) {
    const row = filterDiv.appendChild(document.createElement('div'));
    const key = btoa(serial);
    {
      const showButton = row.appendChild(document.createElement('button'));
      showButton.innerText = 'Show';
      showButton.addEventListener('click', function() {
        console.log(`show ${serial}`);
        for (g of window.charts) {
          setSeriesVisibilityWithPredicate(g, (name) => {
            return serialDict[serial][name] ? true : null;
          });
        }
      });
    }
    {
      const hideButton = row.appendChild(document.createElement('button'));
      hideButton.innerText = 'Hide';
      hideButton.addEventListener('click', function() {
        console.log(`hide ${serial}`);
        for (g of window.charts) {
          setSeriesVisibilityWithPredicate(g, (name) => {
            return serialDict[serial][name] ? false : null;
          });
        }
      });
    }
    {
      const showOnlyButton = row.appendChild(document.createElement('button'));
      showOnlyButton.innerText = 'Only';
      showOnlyButton.addEventListener('click', function() {
        console.log(`only ${serial}`);
        for (g of window.charts) {
          setSeriesVisibilityWithPredicate(g, (name) => {
            return serialDict[serial][name] ? true : false;
          });
        }
      });
    }
    row.appendChild(document.createTextNode(serial));
  }
}

let sync = null;
function updateSync() {
  if (sync) {
    sync.detach();
    sync = null;
  }
  if (window.charts.length >= 2) {
    sync = Dygraph.synchronize(window.charts, {
      range: false,  // Sync x-axis only
      selection: false,
      zoom: true,
    });
  }
}

function xAxisLabelFormatter(d, gran) {
  return d.toISOString().split('T').join('<br>T');
}

document.addEventListener('DOMContentLoaded', async function() {
  const clickInfoDiv = document.getElementById('clickInfo');
  const filterDiv = document.getElementById('filterDiv');
  window.charts = [];
  const params = [
    {path: './data.csv', id: 'chart0', title: 'Tab open latency (ms)'},
    //{path: './x86_pkg_temp.csv', id: 'chart1', title: 'x86_pkg_temp (C)'},
    //{path: './tsr0_temp.csv', id: 'chart2', title: 'TSR0_temp (C)'},
    //{path: './tsr1_temp.csv', id: 'chart3', title: 'TSR1_temp (C)'},
    //{path: './tsr2_temp.csv', id: 'chart4', title: 'TSR2_temp (C)'},
    //{path: './tsr3_temp.csv', id: 'chart5', title: 'TSR3_temp (C)'},
    //{path: './tcpu_pci_temp.csv', id: 'chart6', title: 'TCPU_PCI_temp (C)'},
  ];
  const csvList = [];
  const statusDiv = document.getElementById('statusDiv');
  for (const p of params) {
    let done = false;
    do {
      // Retry loop
      try {
        statusDiv.innerHTML += `<p>Fetching ${p.path}...</p>`;
        const res = await fetch(p.path);
        if (res.status == 404) {
          statusDiv.innerHTML +=
              `<p>404 Not found: ${p.path} - Skipping...</p>`;
          csvList.push('');
          done = true;
          break;
        }
        console.log(res);
        const data = await res.text();
        csvList.push(data);
        statusDiv.innerHTML += `<p>Fetched ${p.path}! ${data.length}</p>`;
        done = true;
        break;
      } catch (e) {
        console.log(e);
        statusDiv.innerHTML += `<p>Failed to fetch ${p.path}. Retrying...</p>`;
        continue;
      }
    } while (!done);
  }
  statusDiv.innerHTML +=
      '<p>Fetch is done. Rendering... please be patient...</p>';
  const chartsDiv = document.getElementById('charts');
  chartsDiv.innerHTML = '';
  for (const i in params) {
    const p = params[i];
    const data = csvList[i];
    if (data === '') {
      // Skip empty data
      continue;
    }
    const div = document.createElement('div');
    div.id = p.id;
    div.className = 'chart';
    chartsDiv.appendChild(div);
    const options = {
      colors: colorPalette,
      connectSeparatedPoints: true,
      drawPoints: true,
      highlightSeriesBackgroundAlpha: 1,
      pointSize: 2,
      highlightSeriesOpts: {strokeWidth: 5, strokeBorderWidth: 3, pointSize: 5},
      strokeWidth: 1,
      strokeBorderWidth: 1,
      legend: 'never',
      rollPeriod: 1,
      showRoller: true,
      title: 'THIS_IS_TEMPLATE',
      hideOverlayOnMouseOut: true,
      axes: {
        x: {
          axisLabelWidth: 150,
          pixelsPerLabel: 100,
          axisLabelFontSize: 10,
          axisLabelFormatter: xAxisLabelFormatter,
        }
      },
      xAxisHeight: 50,
    };
    options.title = p.title;
    options.series = {};
    const seriesNames = data.substr(0, data.indexOf('\n')).split(',').splice(1);
    for (const name of seriesNames) {
      let color = '#c6c6c6';
      if (name.endsWith('mitigations=auto')) {
        color = colorPalette[1];
      } else if (name.endsWith('mitigations=off')) {
        color = colorPalette[0];
      }
      options.series[name] = {color: color};
    }
    const g = new Dygraph(div, data, options);
    var onclick = function(ev) {
      const sname = g.getHighlightSeries();
      const props = g.getPropertiesForSeries(sname);
      if (g.isSeriesLocked()) {
        g.clearSelection();
      } else {
        g.setSelection(g.getSelection(), sname, true);
      }
      clickInfoDiv.innerHTML =
          `Last clicked: <span style="color: ${props.color}">${sname}</span>`;
    };
    g.updateOptions({clickCallback: onclick}, true);
    window.charts.push(g);
  }
  statusDiv.style.display = 'none';
  updateSync();
  updateFilterDiv(window.charts[0])
});
