// charts.js - small reusable Chart.js builders. Keeps a registry so we can
// destroy and rebuild charts cleanly whenever a page re-renders (SPA with
// no framework, so canvases get recreated on every navigation).

const Charts = (() => {
  const registry = {};

  const RISK_COLORS = { Low: "#16a34a", Medium: "#d97706", High: "#ea580c", Critical: "#dc2626", Unscored: "#94a3b8" };
  const PALETTE = ["#2563eb", "#0891b2", "#7c3aed", "#db2777", "#ea580c", "#16a34a", "#ca8a04", "#4338ca"];

  function destroy(id) {
    if (registry[id]) { registry[id].destroy(); delete registry[id]; }
  }

  function donut(canvasId, labels, data, colors) {
    destroy(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    registry[canvasId] = new Chart(ctx, {
      type: "doughnut",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
      options: {
        cutout: "68%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 }, padding: 14 } } },
        maintainAspectRatio: false,
      },
    });
  }

  function riskDonut(canvasId, breakdown) {
    const order = ["Critical", "High", "Medium", "Low", "Unscored"];
    const map = Object.fromEntries(breakdown.map(b => [b.risk_band, b.count]));
    const labels = order.filter(k => map[k]);
    const data = labels.map(k => map[k]);
    const colors = labels.map(k => RISK_COLORS[k]);
    donut(canvasId, labels, data, colors);
  }

  function bar(canvasId, labels, data, opts = {}) {
    destroy(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    registry[canvasId] = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: opts.colors || opts.color || "#2563eb", borderRadius: 5, maxBarThickness: 26 }] },
      options: {
        indexAxis: opts.horizontal ? "y" : "x",
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: opts.tooltipCallbacks } },
        scales: {
          x: { grid: { display: !opts.horizontal }, ticks: { font: { size: 10.5 } } },
          y: { grid: { display: opts.horizontal }, ticks: { font: { size: 10.5 } } },
        },
      },
    });
  }

  function line(canvasId, labels, datasets) {
    destroy(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    registry[canvasId] = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: datasets.map((d, i) => ({
          label: d.label,
          data: d.data,
          borderColor: d.color || PALETTE[i % PALETTE.length],
          backgroundColor: (d.color || PALETTE[i % PALETTE.length]) + "22",
          fill: d.fill !== false,
          tension: 0.35,
          pointRadius: 0,
          borderWidth: 2.2,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10.5 } } },
          y: { grid: { color: "#eef1f6" }, ticks: { font: { size: 10.5 } } },
        },
      },
    });
  }

  function groupedBar(canvasId, labels, datasets) {
    destroy(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    registry[canvasId] = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: datasets.map((d, i) => ({
          label: d.label,
          data: d.data,
          backgroundColor: d.color || PALETTE[i % PALETTE.length],
          borderRadius: 4,
          maxBarThickness: 30,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10.5 } } },
          y: { beginAtZero: true, grid: { color: "#eef1f6" }, ticks: { font: { size: 10.5 } } },
        },
      },
    });
  }

  return { donut, riskDonut, bar, line, groupedBar, RISK_COLORS, PALETTE, destroy };
})();
