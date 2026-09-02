(function () {
  const MAX_TICKERS = 5;
  const validationCache = new Map();

  const els = {
    inputs: document.getElementById("ticker-inputs"),
    periodPills: document.querySelectorAll(".pill[data-period]"),
    customStart: document.getElementById("custom-start"),
    customEnd: document.getElementById("custom-end"),
    clearCustom: document.getElementById("clear-custom"),
    compareBtn: document.getElementById("compare-btn"),
    status: document.getElementById("compare-status"),
    warning: document.getElementById("warning-banner"),
    error: document.getElementById("error-banner"),
    results: document.getElementById("results"),
    tableBody: document.querySelector("#summary-table tbody"),
  };

  let selectedPeriod = "5Y";

  function buildTickerInputs() {
    els.inputs.innerHTML = "";
    for (let i = 0; i < MAX_TICKERS; i++) {
      const row = document.createElement("div");
      row.className = "ticker-row";
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 12;
      input.placeholder = i === 0 ? "VOO" : "ticker";
      input.autocomplete = "off";
      input.spellcheck = false;
      input.dataset.index = i;
      const fb = document.createElement("div");
      fb.className = "ticker-feedback";
      fb.dataset.for = i;
      row.append(input, fb);
      els.inputs.appendChild(row);

      input.addEventListener("blur", () => validateField(input, fb));
      input.addEventListener("input", () => {
        input.classList.remove("invalid");
        fb.textContent = "";
        fb.className = "ticker-feedback";
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); runCompare(); }
      });
    }
  }

  async function validateField(input, fb) {
    const raw = input.value.trim().toUpperCase();
    input.value = raw;
    if (!raw) {
      input.classList.remove("invalid");
      fb.textContent = "";
      fb.className = "ticker-feedback";
      return;
    }
    if (validationCache.has(raw)) {
      applyValidation(input, fb, validationCache.get(raw));
      return;
    }
    fb.textContent = "checking…";
    fb.className = "ticker-feedback";
    try {
      const res = await fetch("/api/validate?ticker=" + encodeURIComponent(raw));
      const data = await res.json();
      validationCache.set(raw, data);
      applyValidation(input, fb, data);
    } catch (e) {
      fb.textContent = "couldn't reach API";
      fb.className = "ticker-feedback bad";
    }
  }

  function applyValidation(input, fb, data) {
    if (data && data.valid) {
      input.classList.remove("invalid");
      fb.textContent = data.name;
      fb.className = "ticker-feedback ok";
    } else {
      input.classList.add("invalid");
      fb.textContent = "not found on Yahoo Finance";
      fb.className = "ticker-feedback bad";
    }
  }

  function collectTickers() {
    return Array.from(els.inputs.querySelectorAll("input"))
      .map(i => i.value.trim().toUpperCase())
      .filter(v => v.length > 0);
  }

  function setBusy(busy) {
    els.compareBtn.disabled = busy;
    if (busy) {
      els.status.innerHTML = '<span class="spinner"></span>fetching data…';
    } else {
      els.status.textContent = "";
    }
  }

  function showWarning(msg) {
    if (!msg) { els.warning.classList.add("hidden"); return; }
    els.warning.textContent = "⚠️ " + msg;
    els.warning.classList.remove("hidden");
  }

  function showError(msg) {
    if (!msg) { els.error.classList.add("hidden"); return; }
    els.error.textContent = msg;
    els.error.classList.remove("hidden");
  }

  function fmtPct(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const cls = v >= 0 ? "pos" : "neg";
    return '<span class="' + cls + '">' + (v >= 0 ? "+" : "") + v.toFixed(2) + "%</span>";
  }

  function renderTable(results) {
    els.tableBody.innerHTML = "";
    results.forEach((r, i) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
          '<span class="ticker-chip" style="background:' + ETFCharts.colorFor(i) + '"></span>' +
          (r.name || "") +
        "</td>" +
        "<td><button type='button' class='fund-link fund-link--mono' data-ticker='" + r.ticker + "'>" + r.ticker + "</button></td>" +
        '<td class="num">' + fmtPct(r.total_return) + "</td>" +
        '<td class="num">' + fmtPct(r.cagr) + "</td>" +
        '<td class="num">' + fmtPct(r.max_drawdown) + "</td>" +
        '<td class="num">' + fmtPct(r.volatility) + "</td>" +
        "<td>" + (r.inception_date || "—") + "</td>" +
        "<td>" + (r.data_start_used || "—") + "</td>";
      els.tableBody.appendChild(tr);
    });
  }

  function buildPayload() {
    const tickers = collectTickers();
    const customStart = els.customStart.value;
    const customEnd = els.customEnd.value;
    const payload = { tickers };
    if (customStart || customEnd) {
      payload.start_date = customStart || null;
      payload.end_date = customEnd || null;
    } else {
      payload.period = selectedPeriod;
    }
    return payload;
  }

  async function runCompare() {
    showError(null);
    showWarning(null);
    const payload = buildPayload();
    if (payload.tickers.length === 0) {
      showError("Enter at least one ticker.");
      return;
    }

    setBusy(true);
    try {
      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.error || "Comparison failed.");
        els.results.classList.add("hidden");
        return;
      }
      if (data.warning) showWarning(data.warning);
      if (data.skipped && data.skipped.length) {
        const note = "Skipped (no Yahoo Finance data): " + data.skipped.join(", ");
        showError(note);
      }
      if (!data.results || data.results.length === 0) {
        els.results.classList.add("hidden");
        if (!data.skipped || !data.skipped.length) showError("No results returned.");
        return;
      }
      ETFCharts.renderAll(data.results);
      renderTable(data.results);
      els.results.classList.remove("hidden");
    } catch (e) {
      showError("Network error: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  function wirePeriodPills() {
    els.periodPills.forEach(btn => {
      btn.addEventListener("click", () => {
        els.periodPills.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedPeriod = btn.dataset.period;
        els.customStart.value = "";
        els.customEnd.value = "";
      });
    });
  }

  function wireCustomRange() {
    function onCustomChange() {
      if (els.customStart.value || els.customEnd.value) {
        els.periodPills.forEach(b => b.classList.remove("active"));
      }
    }
    els.customStart.addEventListener("change", onCustomChange);
    els.customEnd.addEventListener("change", onCustomChange);
    els.clearCustom.addEventListener("click", () => {
      els.customStart.value = "";
      els.customEnd.value = "";
      const def = Array.from(els.periodPills).find(b => b.dataset.period === selectedPeriod);
      if (def) def.classList.add("active");
    });
  }

  // Small API so the Fund Finder tab can push a selection into this tab.
  window.ETFCompare = {
    setTickers(tickers) {
      const inputs = Array.from(els.inputs.querySelectorAll("input"));
      inputs.forEach((inp, i) => {
        inp.value = (tickers[i] || "").toUpperCase();
        inp.classList.remove("invalid");
        const fb = els.inputs.querySelector('.ticker-feedback[data-for="' + i + '"]');
        if (fb) { fb.textContent = ""; fb.className = "ticker-feedback"; }
      });
    },
    run() { runCompare(); },
  };

  document.addEventListener("DOMContentLoaded", () => {
    buildTickerInputs();
    wirePeriodPills();
    wireCustomRange();
    els.compareBtn.addEventListener("click", runCompare);
    // Ticker in the summary table -> open the fund detail modal (from screener.js).
    els.tableBody.addEventListener("click", (e) => {
      const link = e.target.closest(".fund-link");
      if (link && window.FundDetail) window.FundDetail.open(link.dataset.ticker);
    });
  });
})();
