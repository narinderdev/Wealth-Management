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

  initInventoryChartTooltips();
});
