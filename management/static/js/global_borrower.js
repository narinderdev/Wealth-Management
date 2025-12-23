(function () {
  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    var shell = document.querySelector("[data-global-borrower-shell]");
    var select = document.querySelector("[data-global-borrower-select]");
    if (!shell || !select) return;

    var display = document.querySelector("[data-global-borrower-display]");
    var storageKey = "cora-global-borrower";
    var placeholder = "Select Borrower";
    var warningText = "Please select a Borrower from the top bar before creating this record.";
    var noBorrowersText = "No borrowers exist yet. Create a borrower first.";
    var missingSelectionText = "Selected borrower is no longer available.";
    var message = shell.querySelector("[data-global-borrower-message]");
    var createUrl = shell.getAttribute("data-borrower-create-url");
    var currentSelection = null;
    var supportsStorage = (function () {
      try {
        var testKey = "__cora-borrower-test__";
        localStorage.setItem(testKey, "1");
        localStorage.removeItem(testKey);
        return true;
      } catch (err) {
        return false;
      }
    })();

    function hasBorrowerOptions() {
      return Array.prototype.some.call(select.options, function (opt) {
        return opt.value;
      });
    }

    function setHeaderMessage(text) {
      if (!message) return;
      if (text) {
        message.textContent = text;
        message.hidden = false;
      } else {
        message.textContent = "";
        message.hidden = true;
      }
    }

    function updateBorrowerAvailability() {
      var available = hasBorrowerOptions();
      if (!available) {
        select.setAttribute("disabled", "disabled");
      } else {
        select.removeAttribute("disabled");
      }
      shell.setAttribute("data-has-borrowers", available ? "true" : "false");
      return available;
    }

    function findOption(value) {
      if (!value) return null;
      var selectorValue = value;
      if (typeof window.CSS !== "undefined" && CSS.escape) {
        selectorValue = CSS.escape(value);
      } else {
        selectorValue = value.replace(/\"/g, '\\"');
      }
      return select.querySelector('option[value="' + selectorValue + '"]');
    }

    function optionLabel(value) {
      var opt = findOption(value);
      return opt ? opt.textContent.trim() : "";
    }

    function readSelection() {
      if (!supportsStorage) return null;
      try {
        var parsed = JSON.parse(localStorage.getItem(storageKey) || "null");
        if (parsed && parsed.id && optionLabel(parsed.id)) {
          return { id: String(parsed.id), label: parsed.label || optionLabel(parsed.id) };
        }
      } catch (err) {
        return null;
      }
      return null;
    }

    function persistSelection(selection) {
      if (!supportsStorage) return;
      if (selection && selection.id) {
        localStorage.setItem(storageKey, JSON.stringify(selection));
      } else {
        localStorage.removeItem(storageKey);
      }
    }

    function updateBadge(selection) {
      var label = selection && selection.id ? selection.label || optionLabel(selection.id) || placeholder : placeholder;
      if (display) {
        display.textContent = label;
        display.title = label;
      }
      shell.setAttribute("data-has-borrower", selection && selection.id ? "true" : "false");
    }

    function ensureHidden(field) {
      var form = field.closest("form");
      if (!form) return null;
      var name = field.getAttribute("name") || "borrower";
      var hidden = form.querySelector('input[type="hidden"][data-global-borrower-hidden="' + name + '"]');
      if (!hidden) {
        hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = name;
        hidden.setAttribute("data-global-borrower-hidden", name);
        form.appendChild(hidden);
      }
      return hidden;
    }

    function ensureWarning(form) {
      if (!form) return null;
      var warning = form.querySelector(".global-borrower-warning");
      if (!warning) {
        warning = document.createElement("div");
        warning.className = "component-alert global-borrower-warning";
        var body = form.querySelector(".component-modal-body") || form;
        body.insertBefore(warning, body.firstChild);
      }
      return warning;
    }

    function renderWarning(form, text, linkHref, linkText) {
      var warning = ensureWarning(form);
      if (!warning) return null;
      warning.innerHTML = "";
      var messageNode = document.createElement("div");
      messageNode.textContent = text || "";
      warning.appendChild(messageNode);
      if (linkHref && linkText) {
        var link = document.createElement("a");
        link.href = linkHref;
        link.textContent = linkText;
        link.className = "global-borrower-warning__link";
        warning.appendChild(link);
      }
      return warning;
    }

    function toggleWarning(form, shouldShow) {
      var warning = form ? form.querySelector(".global-borrower-warning") : null;
      if (!warning) return;
      warning.style.display = shouldShow ? "block" : "none";
    }

    function toggleSubmit(form, disabled) {
      if (!form) return;
      var submit = form.querySelector('.btn.save[type="submit"]');
      if (!submit) return;
      submit.disabled = disabled;
      submit.classList.toggle("is-disabled", !!disabled);
      submit.setAttribute("aria-disabled", disabled ? "true" : "false");
    }

    function applyToField(field, selection) {
      var form = field.closest("form");
      var actionInput = form ? form.querySelector('input[name="_action"]') : null;
      var action = actionInput ? String(actionInput.value || "").toLowerCase() : "";
      var isCreate = !action || action === "create";
      var hasSelection = !!(selection && selection.id);
      var hidden = ensureHidden(field);
      var currentValue = field.value || "";
      var targetValue = currentValue;

      if (isCreate) {
        targetValue = hasSelection ? selection.id : "";
      } else if (!currentValue && hasSelection) {
        targetValue = selection.id;
      }

      if (hidden) {
        hidden.value = targetValue;
      }

      field.value = targetValue;
      field.setAttribute("disabled", "disabled");
      field.setAttribute("aria-disabled", "true");
      field.classList.add("global-borrower-input");
      field.title = hasSelection ? selection.label || optionLabel(selection.id) || "Borrower selected" : "Select Borrower from header";

      if (isCreate) {
        var borrowersAvailable = hasBorrowerOptions();
        var warningMessage = borrowersAvailable ? warningText : noBorrowersText;
        var warningLink = borrowersAvailable ? null : createUrl;
        var warningLabel = borrowersAvailable ? null : "Go to Borrowers";
        renderWarning(form, warningMessage, warningLink, warningLabel);
        toggleWarning(form, !hasSelection || !borrowersAvailable);
        toggleSubmit(form, !hasSelection || !borrowersAvailable);
      } else {
        toggleWarning(form, false);
        toggleSubmit(form, false);
      }
    }

    function applyToForms(selection, scope) {
      var root = scope || document;
      root.querySelectorAll('[data-global-borrower="true"]').forEach(function (field) {
        applyToField(field, selection);
      });
    }

    function syncSelection(selection) {
      currentSelection = selection && selection.id ? selection : null;
      if (currentSelection) {
        select.value = currentSelection.id;
        persistSelection(currentSelection);
      } else {
        select.value = "";
        persistSelection(null);
      }
      updateBadge(currentSelection);
      applyToForms(currentSelection);
      if (currentSelection) {
        setHeaderMessage("");
      }
    }

    function initialize() {
      updateBorrowerAvailability();
      var stored = readSelection();
      var missingStored = false;
      if (stored && !optionLabel(stored.id)) {
        stored = null;
        persistSelection(null);
        missingStored = true;
      }
      if (stored && optionLabel(stored.id)) {
        syncSelection({ id: String(stored.id), label: stored.label || optionLabel(stored.id) });
      } else {
        syncSelection(null);
      }
      if (missingStored) {
        setHeaderMessage(missingSelectionText);
      }
    }

    select.addEventListener("change", function () {
      setHeaderMessage("");
      var value = select.value;
      var selection = value ? { id: value, label: optionLabel(value) || value } : null;
      syncSelection(selection);
    });

    document.querySelectorAll("[data-modal-open]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var targetId = trigger.getAttribute("data-modal-open");
        if (!targetId) return;
        var modal = document.getElementById(targetId);
        if (modal) {
          applyToForms(currentSelection, modal);
        }
      });
    });

    window.addEventListener("storage", function (event) {
      if (event.key !== storageKey) return;
      var next = readSelection();
      currentSelection = next;
      updateBadge(next);
      applyToForms(next);
      if (next && next.id) {
        select.value = next.id;
      } else {
        select.value = "";
      }
    });

    initialize();
  });
})();
