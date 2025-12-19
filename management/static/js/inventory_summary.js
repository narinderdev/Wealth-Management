document.addEventListener("DOMContentLoaded", () => {
  const initInventoryChartTooltips = () => {
    document.querySelectorAll(".collateral-dynamic .chartPad").forEach(pad => {
      const tooltip = pad.querySelector(".chart-tooltip");
      if (!tooltip) return;

      const showTooltip = (element) => {
        const label = element.dataset.label || "";
        const value = element.dataset.value || "";
        tooltip.innerHTML = "";
        const labelEl = document.createElement("strong");
        labelEl.textContent = label;
        const valueEl = document.createElement("span");
        valueEl.textContent = value;
        tooltip.append(labelEl, valueEl);

        const elemRect = element.getBoundingClientRect();
        const padRect = pad.getBoundingClientRect();
        const left = elemRect.left - padRect.left + (elemRect.width / 2);
        const top = elemRect.top - padRect.top;
        tooltip.style.left = `${Math.max(16, Math.min(padRect.width - 16, left))}px`;
        tooltip.style.top = `${Math.max(18, top - 8)}px`;
        tooltip.classList.add("is-visible");
      };

      const hideTooltip = () => tooltip.classList.remove("is-visible");

      pad.querySelectorAll("[data-label]").forEach(element => {
        element.addEventListener("mouseenter", () => showTooltip(element));
        element.addEventListener("focus", () => showTooltip(element));
        element.addEventListener("mouseleave", hideTooltip);
        element.addEventListener("blur", hideTooltip);
      });
    });
  };

  initInventoryChartTooltips();
});
