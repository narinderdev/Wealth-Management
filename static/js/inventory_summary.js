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

  initInventoryChartTooltips();
  drawLineCharts();

  let resizeTimer;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(drawLineCharts, 120);
  });
});
