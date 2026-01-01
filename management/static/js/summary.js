const onReady = (callback) => {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', callback);
  } else {
    callback();
  }
};

onReady(() => {
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
      if (btn.getAttribute('aria-disabled') === 'true') {
        return;
      }
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

  const parseChartData = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    const raw = (el.textContent || '').trim();
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === 'string') {
        return JSON.parse(parsed);
      }
      return parsed;
    } catch (error) {
      return null;
    }
  };

  const coerceNumber = (value) => {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') {
      return Number.isFinite(value) ? value : null;
    }
    if (typeof value === 'string') {
      const cleaned = value.replace(/[$,]/g, '');
      const parsed = Number(cleaned);
      return Number.isFinite(parsed) ? parsed : null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '';
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
      const padding = Math.abs(min) * 0.1 || 1;
      min -= padding;
      max += padding;
    } else {
      const pad = Math.max(Math.abs(max - min) * 0.1, 1);
      min -= pad;
      max += pad;
    }
    return { min, max };
  };

  const initKpiChart = (canvasId, dataId, color) => {
    const canvas = document.getElementById(canvasId);
    const data = parseChartData(dataId);
    if (!canvas || !data || !Array.isArray(data.values) || !data.values.length) return;
    if (typeof Chart === 'undefined') return;

    const chartValues = data.values.map(coerceNumber);
    const hasValues = chartValues.some((val) => Number.isFinite(val));
    if (!hasValues) return;

    const bounds = buildAxisBounds(chartValues);
    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: Array.isArray(data.labels) ? data.labels : [],
        datasets: [
          {
            data: chartValues,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 4,
            tension: 0.25,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => formatCurrency(context.parsed.y),
            },
          },
        },
        scales: {
          x: {
            grid: { color: '#E7ECF5' },
            ticks: { color: '#98A2B3' },
          },
          y: {
            grid: { color: '#E7ECF5' },
            ticks: {
              color: '#98A2B3',
              callback: (value) => formatCurrency(value),
            },
            min: bounds ? bounds.min : undefined,
            max: bounds ? bounds.max : undefined,
          },
        },
      },
    });
  };

  const loadChartJs = (callback) => {
    if (typeof Chart !== 'undefined') {
      callback();
      return;
    }
    const fallback = document.getElementById('chartjs-fallback');
    const src = fallback ? fallback.dataset.src : null;
    if (!src) return;
    const script = document.createElement('script');
    script.src = src;
    script.onload = callback;
    document.head.appendChild(script);
  };

  const initKpiCharts = () => {
    initKpiChart('netChart', 'net-chart-data', '#2F6BFF');
    initKpiChart('outstandingChart', 'outstanding-chart-data', '#7C3AED');
    initKpiChart('availabilityChart', 'availability-chart-data', '#13B26B');
  };

  loadChartJs(initKpiCharts);
});
