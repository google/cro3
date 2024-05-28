const colorPalette = [
  '#e60049', '#0bb4ff', '#50e991', '#e6d800', '#9b19f5', '#ffa300', '#dc0ab4',
  '#b3d4ff', '#00bfa0', '#ea5545', '#bdcf32', '#b30000', '#7c1158', '#4421af',
  '#1a53ff', '#0d88e6', '#00b7c7', '#5ad45a', '#8be04e', '#ebdc78',
];

function setSeriesVisibility(g, name, visible) {
  const key = btoa(name);
  const labelNode = document.getElementById(`filter_${key}`);
  let props = g.getPropertiesForSeries(name);
  const idx = g.indexFromSetName(name) - 1;
  g.setVisibility(idx, visible);
  if (visible) {
    props = g.getPropertiesForSeries(name);
    labelNode.style.color = props.color;
  } else {
    labelNode.style.color = '#c0c0c0';
  }
}
function hideSeries(g, name) {
  setSeriesVisibility(g, name, false);
}
function showSeries(g, name) {
  setSeriesVisibility(g, name, true);
}

function createFilterLabels(name) {
  const row = document.createElement('div');
  const key = btoa(name);
  row.innerHTML = `<span class="toggleLabel" id="filter_${
      key}" onclick="toggleSeriesVisibility('${name}')">${name}</span>`;
  return row;
}

function updateFilterDiv(g) {
  const labels = g.getLabels().splice(1);
  const filterDiv = document.getElementById('filterDiv');
  const hwidDict = {};

  for (const labelIndex in labels) {
    const label = labels[labelIndex];
    const labelElements = label.split('/');
    const hwid = labelElements[0];
    if (hwidDict[hwid] === undefined) {
      hwidDict[hwid] = {};
    }
    hwidDict[hwid][label] = true;
  }

  filterDiv.innerHTML = '';
  window.filterDiv = filterDiv;
  filterDiv.append("<h2>HWID</h2>");
  for (const hwid in hwidDict) {
    const row = filterDiv.appendChild(document.createElement('div'));
    const key = btoa(hwid);
    {
      const showButton = row.appendChild(document.createElement('button'));
      showButton.innerText = 'Show';
      showButton.addEventListener("click", function() {
        console.log(`show ${hwid}`);
        for (const seriesName in hwidDict[hwid]) {
          for (g of window.charts) {
            showSeries(g, seriesName);
          }
        }
      });
    }
    {
      const hideButton = row.appendChild(document.createElement('button'));
      hideButton.innerText = 'Hide';
      hideButton.addEventListener("click", function() {
        console.log(`hide ${hwid}`);
        for (const seriesName in hwidDict[hwid]) {
          for (g of window.charts) {
            hideSeries(g, seriesName);
          }
        }
      });
    }
    row.appendChild(document.createTextNode(hwid));
  }

  filterDiv.append("<h2>Series</h2>");
  for (const labelIndex in labels) {
    const label = labels[labelIndex];
    const labelNode = createFilterLabels(label);
    labelNode.style.color = colorPalette[labelIndex % colorPalette.length];
    filterDiv.append(labelNode);
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

document.addEventListener('DOMContentLoaded', async function() {
  const clickInfoDiv = document.getElementById('clickInfo');
  const filterDiv = document.getElementById('filterDiv');
  window.charts = [];
  const baseOptions = {
    colors: colorPalette,
    connectSeparatedPoints: true,
    drawPoints: true,
    highlightCircleSize: 5,
    highlightSeriesOpts:
        {strokeWidth: 3, strokeBorderWidth: 1, highlightCircleSize: 5},
    legend: 'never',
    pointSize: 1,
    rollPeriod: 1,
    showRoller: true,
    strokeBorderWidth: 1,
    strokeWidth: 0.5,
    title: 'THIS_IS_TEMPLATE',
    hideOverlayOnMouseOut: true,
  };
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
    const options = structuredClone(baseOptions);
    options.title = p.title;
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
