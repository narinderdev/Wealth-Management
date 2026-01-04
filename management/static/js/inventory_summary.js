document.addEventListener("DOMContentLoaded", () => {
  const initInventoryChartTooltips = () => {
    document.querySelectorAll(".collateral-dynamic .chartPad").forEach(pad => {
      const tooltip = pad.querySelector(".chart-tooltip");
      if (!tooltip) return;

      const showTooltip = (event) => {
        const element = event.currentTarget;
        const label = element.dataset.label || "";
        const value = element.dataset.value || "";
        tooltip.innerHTML = "";
        const labelEl = document.createElement("strong");
        labelEl.textContent = label;
        const valueEl = document.createElement("span");
        valueEl.textContent = value;
        tooltip.append(labelEl, valueEl);

        const padRect = pad.getBoundingClientRect();
        const x = event.clientX - padRect.left;
        const y = event.clientY - padRect.top;
        tooltip.style.left = `${Math.max(12, Math.min(padRect.width - 12, x))}px`;
        tooltip.style.top = `${Math.max(18, Math.min(padRect.height - 18, y - 10))}px`;
        tooltip.classList.add("is-visible");
      };

      const hideTooltip = () => tooltip.classList.remove("is-visible");

      pad.querySelectorAll("[data-label]").forEach(element => {
        element.style.cursor = "pointer";
        element.addEventListener("mousemove", showTooltip);
        element.addEventListener("mouseenter", showTooltip);
        element.addEventListener("focus", showTooltip);
        element.addEventListener("mouseleave", hideTooltip);
        element.addEventListener("blur", hideTooltip);
      });
    });
  };

  const parseJsonString = (raw) => {
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return "—";
    const abs = Math.abs(value);
    if (abs >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
    if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
    if (abs >= 1_000) return `$${Math.round(value / 1_000)}k`;
    return `$${Math.round(value).toLocaleString()}`;
  };

  const buildAxisBounds = (values) => {
    const filtered = values.filter((val) => Number.isFinite(val));
    if (!filtered.length) return null;
    let min = Math.min(...filtered);
    let max = Math.max(...filtered);
    if (min === max) {
      const pad = Math.abs(max) * 0.1 || 1;
      return { min: min - pad, max: max + pad };
    }
    const yMax = max * 1.1;
    let yMin = min;
    if (min > 0) {
      yMin = min * 0.9;
    } else if (min < 0) {
      yMin = min - Math.abs(min * 0.1);
    } else {
      yMin = 0;
    }
    return { min: yMin, max: yMax };
  };

  const loadChartJs = (callback) => {
    if (typeof Chart !== "undefined") {
      callback();
      return;
    }
    const fallback = document.getElementById("chartjs-fallback");
    const src = fallback ? fallback.dataset.src : null;
    if (!src) return;
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      existing.addEventListener("load", callback);
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.dataset.chartjsLoader = "true";
    script.onload = callback;
    document.head.appendChild(script);
  };

  const parseLinePoints = (raw) => {
    if (!raw) return [];
    return raw.trim().split(/\s+/).map(pair => {
      const parts = pair.split(",");
      const x = parseFloat(parts[0]);
      const y = parseFloat(parts[1]);
      if (Number.isNaN(x) || Number.isNaN(y)) {
        return null;
      }
      return { x, y };
    }).filter(Boolean);
  };

  const drawLineCharts = () => {
    document.querySelectorAll(".chart-canvas[data-line-points]").forEach(canvas => {
      const points = parseLinePoints(canvas.dataset.linePoints);
      if (!points.length) return;
      const width = parseFloat(canvas.dataset.chartWidth || "0");
      const height = parseFloat(canvas.dataset.chartHeight || "0");
      if (!width || !height) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.strokeStyle = canvas.dataset.lineColor || "#0b5bd3";
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.beginPath();
      points.forEach((point, idx) => {
        if (idx === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.stroke();
    });
  };

  const initInventoryMixTrendChart = () => {
    const canvas = document.querySelector(".inventory-mix-chart");
    if (!canvas) return;
    const dataEl = document.getElementById("inventoryMixTrendData");
    const payload = dataEl ? parseJsonString(dataEl.textContent || "") : null;
    if (!payload || !Array.isArray(payload.labels) || !Array.isArray(payload.series)) {
      canvas.parentElement.innerHTML = `<div class="card-pad">No data available.</div>`;
      return;
    }
    if (!payload.labels.length || !payload.series.length) {
      canvas.parentElement.innerHTML = `<div class="card-pad">No data available.</div>`;
      return;
    }
    const seriesValues = payload.series
      .map((series) => (Array.isArray(series.values) ? series.values : []))
      .flat()
      .map((val) => (typeof val === "string" ? Number(val.replace(/[$,]/g, "")) : Number(val)));
    const bounds = buildAxisBounds(seriesValues);
    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: payload.labels,
        datasets: payload.series.map((series) => {
          const values = Array.isArray(series.values)
            ? series.values.map((val) => {
                const parsed = typeof val === "string" ? Number(val.replace(/[$,]/g, "")) : Number(val);
                return Number.isFinite(parsed) ? parsed : null;
              })
            : [];
          return {
            label: series.label,
            data: values,
            borderColor: series.color || "#0b5bd3",
            backgroundColor: series.color || "#0b5bd3",
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 4,
            tension: 0.25,
            spanGaps: true,
          };
        }),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => (items.length ? items[0].label : ""),
              label: (context) => `${context.dataset.label}: ${formatCurrency(context.parsed.y)}`,
            },
          },
        },
        scales: {
          x: { grid: { color: "#E7ECF5" }, ticks: { color: "#98A2B3" } },
          y: {
            grid: { color: "#E7ECF5" },
            ticks: { color: "#98A2B3", callback: (value) => formatCurrency(value) },
            min: bounds ? bounds.min : undefined,
            max: bounds ? bounds.max : undefined,
          },
        },
      },
    });
  };

  initInventoryChartTooltips();
  drawLineCharts();
  loadChartJs(initInventoryMixTrendChart);

  let resizeTimer;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(drawLineCharts, 120);
  });
});
