const DATA_URL = "../outputs/webapp_data.json";

const chartConfig = {
  displayModeBar: false,
  responsive: true,
};

function formatNumber(value) {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  return String(value);
}

function fillStats(stats) {
  document.querySelectorAll("[data-stat]").forEach((el) => {
    const key = el.dataset.stat;
    if (key in stats) {
      el.textContent = formatNumber(stats[key]);
    }
  });
}

function fillAbstract(abstract) {
  document.querySelectorAll("[data-abstract]").forEach((el) => {
    const key = el.dataset.abstract;
    if (key in abstract) {
      el.textContent = abstract[key];
    }
  });
}

function plotBandChart(elementId, xValues, median, lower, upper, color) {
  const lowerTrace = {
    x: xValues,
    y: lower,
    type: "scatter",
    mode: "lines",
    line: { color: "rgba(0,0,0,0)" },
    hoverinfo: "skip",
    showlegend: false,
  };
  const upperTrace = {
    x: xValues,
    y: upper,
    type: "scatter",
    mode: "lines",
    line: { color: "rgba(0,0,0,0)" },
    fill: "tonexty",
    fillcolor: `${color}33`,
    hoverinfo: "skip",
    showlegend: false,
  };
  const medianTrace = {
    x: xValues,
    y: median,
    type: "scatter",
    mode: "lines+markers",
    line: { color, width: 2 },
    marker: { size: 6 },
    name: "Median",
  };

  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 45 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    xaxis: { title: "Sample size (N)", gridcolor: "rgba(0,0,0,0.08)" },
    yaxis: { title: "Metric", gridcolor: "rgba(0,0,0,0.08)" },
    showlegend: false,
  };

  Plotly.newPlot(elementId, [lowerTrace, upperTrace, medianTrace], layout, chartConfig);
}

function renderAggregateCharts(aggData) {
  const x = aggData.map((row) => row.N);
  plotBandChart(
    "aggregate-mae",
    x,
    aggData.map((row) => row.mae_median),
    aggData.map((row) => row.mae_p25),
    aggData.map((row) => row.mae_p75),
    "#1f5a5c"
  );

  plotBandChart(
    "aggregate-bottom",
    x,
    aggData.map((row) => row.bottom_decile_median),
    aggData.map((row) => row.bottom_decile_p25),
    aggData.map((row) => row.bottom_decile_p75),
    "#b24a2b"
  );
}

function renderProtocolMeta(meta) {
  const fallback = {
    plans_total: "--",
    plans_eligible: "--",
    constraints_total: "--",
    constraints_with_values: "--",
  };
  const payload = meta || fallback;
  document.querySelectorAll("[data-protocol]").forEach((el) => {
    const key = el.dataset.protocol;
    el.textContent = formatNumber(payload[key] ?? "--");
  });
}

function renderProtocolCharts(curve, aggregateLabel) {
  if (!curve || curve.length === 0) {
    renderProtocolMeta(null);
    return;
  }
  const x = curve.map((row) => row.N);
  const charts = [
    { id: "protocol-mae", key: "mae_median", color: "#1f5a5c" },
    { id: "protocol-ks", key: "ks_median", color: "#5b6b2b" },
    { id: "protocol-wass", key: "wasserstein_median", color: "#b24a2b" },
    { id: "protocol-bottom", key: "bottom_decile_agreement_median", color: "#8a4a7d" },
  ];

  charts.forEach((chart) => {
    const trace = {
      x,
      y: curve.map((row) => row[chart.key]),
      type: "scatter",
      mode: "lines+markers",
      line: { color: chart.color, width: 2 },
      marker: { size: 6 },
      name: aggregateLabel,
    };
    const layout = {
      margin: { t: 10, r: 10, b: 40, l: 45 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { title: "Sample size (N)", gridcolor: "rgba(0,0,0,0.08)" },
      yaxis: { title: "Metric", gridcolor: "rgba(0,0,0,0.08)" },
      showlegend: false,
    };
    Plotly.newPlot(chart.id, [trace], layout, chartConfig);
  });
}

function setupProtocolExplorer(protocols, curves, aggregateCurve) {
  const select = document.getElementById("protocol-select");
  const sorted = protocols.slice().sort((a, b) => b.plans_eligible - a.plans_eligible);

  const aggregateOption = document.createElement("option");
  aggregateOption.value = "__aggregate__";
  aggregateOption.textContent = "Aggregate (All Protocols)";
  select.appendChild(aggregateOption);

  sorted.forEach((protocol) => {
    const option = document.createElement("option");
    option.value = protocol.protocol;
    option.textContent = protocol.protocol;
    select.appendChild(option);
  });

  const metaLookup = {};
  protocols.forEach((row) => {
    metaLookup[row.protocol] = row;
  });

  function handleSelection() {
    const value = select.value;
    if (value === "__aggregate__") {
      renderProtocolMeta(null);
      renderProtocolCharts(aggregateCurve, "Aggregate");
      return;
    }
    const curve = curves[value] || [];
    renderProtocolMeta(metaLookup[value]);
    renderProtocolCharts(curve, value);
  }

  select.addEventListener("change", handleSelection);
  select.value = "__aggregate__";
  handleSelection();
}

async function initDashboard() {
  const response = await fetch(DATA_URL);
  const data = await response.json();

  fillStats(data.stats);
  fillAbstract(data.abstract);
  renderAggregateCharts(data.learning_curve);
  setupProtocolExplorer(data.protocols, data.protocol_curves, data.learning_curve);
}

document.addEventListener("DOMContentLoaded", () => {
  const printButton = document.getElementById("print-button");
  if (printButton) {
    printButton.addEventListener("click", () => window.print());
  }
  initDashboard().catch((error) => {
    console.error("Failed to load dashboard data:", error);
  });
});
