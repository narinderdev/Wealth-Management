document.addEventListener('DOMContentLoaded', () => {
  const initLegacyToggles = () => {
    const toggles = document.querySelectorAll('.row-toggle');
    if (!toggles.length) return;

    const hideDescendants = (id) => {
      if (!id) return;
      document.querySelectorAll(`[data-parent="${id}"]`).forEach(row => {
        row.classList.add('row-hidden');
        const childToggle = row.querySelector('.row-toggle');
        if (childToggle) childToggle.setAttribute('aria-expanded', 'false');
        hideDescendants(row.dataset.id);
      });
    };

    toggles.forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.row;
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        if (expanded) {
          btn.setAttribute('aria-expanded', 'false');
          hideDescendants(target);
        } else {
          btn.setAttribute('aria-expanded', 'true');
          document.querySelectorAll(`[data-parent="${target}"]`).forEach(row => {
            row.classList.remove('row-hidden');
          });
        }
      });
    });
  };

  const initCollateralToggles = () => {
    const toggles = document.querySelectorAll('.cc-toggle');
    if (!toggles.length) return;

    const hideDescendants = (parentId) => {
      document.querySelectorAll(`tr[data-parent="${parentId}"]`).forEach(tr => {
        tr.classList.add('is-hidden');
        const childId = tr.dataset.id;
        const childBtn = tr.querySelector('.cc-toggle');
        if (childBtn) childBtn.setAttribute('aria-expanded', 'false');
        hideDescendants(childId);
      });
    };

    toggles.forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.row;
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', String(!expanded));
        if (!expanded) {
          document.querySelectorAll(`tr[data-parent="${id}"]`).forEach(tr => {
            tr.classList.remove('is-hidden');
          });
        } else {
          hideDescendants(id);
        }
      });
    });
  };

  initLegacyToggles();
  initCollateralToggles();

  const initChartTooltips = () => {
    document.querySelectorAll('.panel-chart').forEach(chart => {
      const tooltip = chart.querySelector('.chart-tooltip');
      if (!tooltip) return;
      const circles = chart.querySelectorAll('.panel-dots circle');
      const showTooltip = (event, circle) => {
        const label = circle.dataset.label || '';
        const value = circle.dataset.value || '';
        tooltip.innerHTML = '';
        const labelEl = document.createElement('strong');
        labelEl.textContent = label;
        const valueEl = document.createElement('span');
        valueEl.textContent = value;
        tooltip.append(labelEl, valueEl);
        const circleRect = circle.getBoundingClientRect();
        const chartRect = chart.getBoundingClientRect();
        const left = circleRect.left - chartRect.left + (circleRect.width / 2);
        const top = circleRect.top - chartRect.top - 30;
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
        tooltip.classList.add('is-visible');
      };
      const hideTooltip = () => tooltip.classList.remove('is-visible');
      circles.forEach(circle => {
        circle.addEventListener('mouseenter', event => showTooltip(event, circle));
        circle.addEventListener('focus', event => showTooltip(event, circle));
        circle.addEventListener('mouseleave', hideTooltip);
        circle.addEventListener('blur', hideTooltip);
      });
    });
  };

  const initRiskTooltip = () => {
    const circle = document.querySelector('.risk-circle');
    const tooltip = document.querySelector('.risk-tooltip');
    if (!circle || !tooltip) return;
    const show = () => {
      tooltip.textContent = circle.dataset.tooltip || '';
      const circleRect = circle.getBoundingClientRect();
      const parentRect = circle.closest('.risk').getBoundingClientRect();
      tooltip.style.left = `${circleRect.left - parentRect.left}px`;
      tooltip.style.top = `${circleRect.bottom - parentRect.top + 10}px`;
      tooltip.classList.add('is-visible');
    };
    const hide = () => tooltip.classList.remove('is-visible');
    circle.addEventListener('mouseenter', show);
    circle.addEventListener('mouseleave', hide);
    circle.addEventListener('focus', show);
    circle.addEventListener('blur', hide);
  };

  initChartTooltips();
  initRiskTooltip();
});
