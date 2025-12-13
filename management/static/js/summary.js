 document.addEventListener('DOMContentLoaded', () => {
    const toggles = document.querySelectorAll('.row-toggle');

    const hideDescendants = (id) => {
      if (!id) return;
      document.querySelectorAll(`[data-parent="${id}"]`).forEach(row => {
        row.classList.add('row-hidden');
        const childToggle = row.querySelector('.row-toggle');
        if (childToggle) {
          childToggle.setAttribute('aria-expanded', 'false');
        }
        const childId = row.dataset.id;
        if (childId) {
          hideDescendants(childId);
        }
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
  });