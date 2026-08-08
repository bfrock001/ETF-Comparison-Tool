(function (global) {
  // Beyond the Noise — Editorial accents (+ soft neutral as 5th)
  const PALETTE = ["#1E3A5F", "#2C7370", "#C44A30", "#B8932A", "#57534A"];
  const GRID = "rgba(27, 33, 41, 0.10)";
  const INK = "#1B2129";
  const SOFT = "#57534A";
  const charts = {};

  if (typeof Chart !== "undefined") {
    Chart.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = SOFT;
    Chart.defaults.borderColor = GRID;
  }

  function colorFor(i) { return PALETTE[i % PALETTE.length]; }

  function destroy(key) {
    if (charts[key]) { charts[key].destroy(); delete charts[key]; }
  }

  const numberFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
  const currencyFmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const dateFmt = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" });

  function pctTooltip(value) { return numberFmt.format(value) + "%"; }

  function barChart(canvasId, key, label, results, valueAccessor, opts) {
    destroy(key);
    const ctx = document.getElementById(canvasId).getContext("2d");
    const labels = results.map(r => r.ticker);
    const data = results.map(valueAccessor);
    const colors = results.map((_, i) => colorFor(i));

    charts[key] = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label,
          data,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => " " + (opts && opts.tooltipLabel ? opts.tooltipLabel(ctx.parsed.y) : pctTooltip(ctx.parsed.y)),
            },
          },
        },
        scales: {
          y: {
            ticks: { callback: v => v + "%" },
            grid: { color: GRID },
            beginAtZero: opts && opts.beginAtZero,
          },
          x: {
            grid: { display: false },
          },
        },
      },
    });
  }

  function renderTotalReturnChart(results) {
    barChart("chart-total-return", "totalReturn", "Total Return", results, r => r.total_return, { beginAtZero: true });
  }

  function renderVolatilityChart(results) {
    barChart("chart-volatility", "volatility", "Annualized Volatility", results, r => r.volatility, { beginAtZero: true });
  }

  function renderDrawdownChart(results) {
    barChart("chart-drawdown", "drawdown", "Max Drawdown", results, r => r.max_drawdown, { beginAtZero: false });
  }

  function renderGrowthChart(results) {
    destroy("growth");
    const ctx = document.getElementById("chart-growth").getContext("2d");

    const datasets = results.map((r, i) => {
      const c = colorFor(i);
      return {
        label: r.ticker,
        data: r.growth_series.dates.map((d, j) => ({ x: d, y: r.growth_series.values[j] })),
        borderColor: c,
        backgroundColor: c,
        pointRadius: 0,
        borderWidth: 2,
        tension: 0,
      };
    });

    charts.growth = new Chart(ctx, {
      type: "line",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true } },
          tooltip: {
            callbacks: {
              title: (items) => items.length ? dateFmt.format(new Date(items[0].parsed.x)) : "",
              label: (ctx) => " " + ctx.dataset.label + ": " + currencyFmt.format(ctx.parsed.y),
            },
          },
        },
        scales: {
          x: {
            type: "time",
            time: { unit: "year" },
            grid: { color: GRID },
            ticks: { autoSkip: true, maxTicksLimit: 8 },
          },
          y: {
            ticks: { callback: v => "$" + numberFmt.format(v) },
            grid: { color: GRID },
          },
        },
      },
    });
  }

  function renderAll(results) {
    renderTotalReturnChart(results);
    renderVolatilityChart(results);
    renderDrawdownChart(results);
    renderGrowthChart(results);
  }

  global.ETFCharts = { renderAll, colorFor, PALETTE };
})(window);
