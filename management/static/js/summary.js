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
});
