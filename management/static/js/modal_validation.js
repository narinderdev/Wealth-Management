(function () {
  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function escapeSelector(value) {
    if (!value) return "";
    if (typeof window.CSS !== "undefined" && CSS.escape) {
      return CSS.escape(value);
    }
    return String(value).replace(/("|'|\\)/g, "\\$1");
  }

  function toArray(list) {
    return Array.prototype.slice.call(list || []);
  }

  function isFieldVisible(field) {
    if (!field || field.type === "hidden") return false;
    if (field.closest("[hidden]")) return false;
    var style = window.getComputedStyle(field);
    if (style.display === "none" || style.visibility === "hidden") return false;
    if (field.offsetParent === null && style.position !== "fixed") return false;
    return true;
  }

  function isRequiredField(field) {
    if (!field) return false;
    var required = field.hasAttribute("required") || field.getAttribute("aria-required") === "true";
    var dataRequired = field.getAttribute("data-required");
    if (dataRequired) {
      var normalized = String(dataRequired).toLowerCase();
      if (normalized === "true" || normalized === "1" || normalized === "yes") {
        required = true;
      }
    }
    return required;
  }

  function getFieldLabel(field) {
    if (!field) return "This field";
    var labelText = field.getAttribute("data-field-label") || "";
    var labelElement = null;
    var id = field.getAttribute("id");
    if (id) {
      var selector = 'label[for="' + escapeSelector(id) + '"]';
      labelElement = field.form ? field.form.querySelector(selector) : document.querySelector(selector);
    }
    if (!labelElement) {
      var wrapper = field.closest(".component-field");
      if (wrapper) {
        labelElement = wrapper.querySelector("label");
      }
    }
    var text = labelElement && labelElement.textContent ? labelElement.textContent.trim() : "";
    if (text.endsWith("*")) {
      text = text.slice(0, -1).trim();
    }
    if (text) return text;
    if (labelText) return labelText;
    var name = field.getAttribute("name");
    return name ? name.replace(/_/g, " ").trim() || "This field" : "This field";
  }

  function hasGlobalBorrowerValue(field) {
    if (!field || field.getAttribute("data-global-borrower") !== "true") return "";
    var form = field.closest("form");
    if (!form) return "";
    var name = field.getAttribute("name") || "borrower";
    var hidden =
      form.querySelector('input[type="hidden"][data-global-borrower-hidden="' + name + '"]') ||
      form.querySelector('input[type="hidden"][data-global-borrower-hidden]');
    return hidden && hidden.value ? hidden.value : "";
  }

  function isPlaceholderValue(value) {
    var trimmed = String(value || "").trim();
    if (!trimmed) return true;
    if (trimmed === "---" || trimmed === "--") return true;
    return false;
  }

  function getFieldValue(field) {
    if (!field) return "";
    var tag = (field.tagName || "").toLowerCase();
    var type = (field.getAttribute("type") || "").toLowerCase();

    if (tag === "select") {
      if (field.multiple) {
        var selected = toArray(field.selectedOptions).map(function (opt) {
          return opt.value;
        });
        return selected.length ? selected : "";
      }
      return field.value || "";
    }

    if (type === "checkbox") {
      return field.checked ? "checked" : "";
    }

    if (type === "radio") {
      var form = field.closest("form");
      var radios = form ? form.querySelectorAll('input[type="radio"][name="' + field.name + '"]') : [field];
      var checked = Array.prototype.some.call(radios, function (radio) {
        return radio.checked;
      });
      return checked ? "checked" : "";
    }

    return field.value || "";
  }

  function ensureErrorElement(field) {
    var wrapper = field.closest(".component-field") || field.parentNode;
    if (!wrapper) return null;
    var existing = wrapper.querySelector(".js-validation-error");
    if (existing) return existing;
    var error = document.createElement("div");
    error.className = "component-error js-validation-error";
    wrapper.appendChild(error);
    return error;
  }

  function updateDescribedBy(field, errorId, add) {
    if (!errorId) return;
    var current = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    var index = current.indexOf(errorId);
    if (add && index === -1) {
      current.push(errorId);
    }
    if (!add && index !== -1) {
      current.splice(index, 1);
    }
    if (current.length) {
      field.setAttribute("aria-describedby", current.join(" "));
    } else {
      field.removeAttribute("aria-describedby");
    }
  }

  function setFieldError(field, message) {
    var wrapper = field.closest(".component-field") || field.parentNode;
    var errorEl = ensureErrorElement(field);
    if (!errorEl) return;
    var errorId = field.getAttribute("data-validation-error-id");
    if (!errorId) {
      var base = field.getAttribute("id") || field.getAttribute("name") || "field";
      errorId = base + "-validation-error";
      field.setAttribute("data-validation-error-id", errorId);
    }
    errorEl.id = errorId;
    errorEl.textContent = message;
    errorEl.hidden = false;
    if (wrapper && wrapper.classList) {
      wrapper.classList.add("has-error");
    }
    field.classList.add("is-invalid");
    field.setAttribute("aria-invalid", "true");
    updateDescribedBy(field, errorId, true);
  }

  function clearFieldError(field) {
    var wrapper = field.closest(".component-field") || field.parentNode;
    var errorEl = wrapper ? wrapper.querySelector(".js-validation-error") : null;
    if (errorEl) {
      errorEl.remove();
    }
    if (wrapper && wrapper.classList) {
      wrapper.classList.remove("has-error");
    }
    var errorId = field.getAttribute("data-validation-error-id");
    updateDescribedBy(field, errorId, false);
    field.classList.remove("is-invalid");
    field.removeAttribute("aria-invalid");
  }

  function ensureSummary(modal) {
    var body = modal.querySelector(".component-modal-body") || modal;
    var summary = body.querySelector(".modal-validation-summary");
    if (summary) return summary;
    summary = document.createElement("div");
    summary.className = "modal-validation-summary component-error";
    summary.setAttribute("role", "alert");
    summary.setAttribute("aria-live", "polite");
    summary.hidden = true;
    body.insertBefore(summary, body.firstChild);
    return summary;
  }

  function renderSummary(modal, errors) {
    var summary = ensureSummary(modal);
    if (!errors.length) {
      summary.hidden = true;
      summary.innerHTML = "";
      return;
    }
    var unique = [];
    errors.forEach(function (error) {
      if (!error || !error.label) return;
      var text = error.label + ": " + error.message;
      if (unique.indexOf(text) === -1) {
        unique.push(text);
      }
    });
    summary.innerHTML = "";
    var intro = document.createElement("div");
    intro.textContent = "Please fix the highlighted fields:";
    summary.appendChild(intro);
    var list = document.createElement("ul");
    unique.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    summary.appendChild(list);
    summary.hidden = false;
  }

  function clearModalValidation(modal) {
    var form = modal.querySelector("form.component-form");
    if (!form) return;
    var summary = modal.querySelector(".modal-validation-summary");
    if (summary) {
      summary.hidden = true;
      summary.innerHTML = "";
    }
    var fields = form.querySelectorAll("input, select, textarea");
    toArray(fields).forEach(function (field) {
      clearFieldError(field);
    });
  }

  function validateRadioGroup(form, sampleField, radioCache) {
    var name = sampleField.getAttribute("name");
    if (!name) return null;
    if (radioCache[name]) return null;
    radioCache[name] = true;

    var required = isRequiredField(sampleField);
    if (!required) return null;
    var radios = toArray(form.querySelectorAll('input[type="radio"][name="' + name + '"]'));
    var label = getFieldLabel(sampleField);
    var hasVisible = false;
    var isChecked = false;

    radios.forEach(function (radio) {
      if (radio.disabled) return;
      if (!isFieldVisible(radio)) return;
      hasVisible = true;
      if (radio.checked) {
        isChecked = true;
      }
    });

    if (!hasVisible) return null;
    if (isChecked) return null;
    return { field: sampleField, label: label, message: "This field is required." };
  }

  function validateField(field, form) {
    var required = isRequiredField(field);
    var visible = isFieldVisible(field);
    var tag = (field.tagName || "").toLowerCase();
    var type = (field.getAttribute("type") || "").toLowerCase();
    var name = (field.getAttribute("name") || "").toLowerCase();
    var label = getFieldLabel(field);

    if (hasGlobalBorrowerValue(field)) {
      return null;
    }

    if (!visible) {
      return null;
    }

    if (field.disabled && !required) {
      return null;
    }

    var rawValue = getFieldValue(field);
    var isEmpty = false;

    if (tag === "select") {
      if (field.multiple) {
        isEmpty = !rawValue || !rawValue.length;
      } else {
        isEmpty = isPlaceholderValue(rawValue);
      }
    } else if (type === "checkbox") {
      isEmpty = rawValue !== "checked";
    } else if (type === "radio") {
      // handled separately
      return null;
    } else {
      isEmpty = String(rawValue).trim() === "";
    }

    if (required && isEmpty) {
      return { field: field, label: label, message: "This field is required." };
    }

    if (!required && isEmpty) {
      return null;
    }

    if (type === "email" || name.indexOf("email") !== -1) {
      var trimmedEmail = String(rawValue).trim();
      if (type === "email" && field.validity) {
        if (!field.validity.valid) {
          return { field: field, label: label, message: "Enter a valid email address." };
        }
      } else {
        // Sanity: pass abc@xyz.com, john.doe+1@company.co.uk, a@b.com
        // Fail abc@, @xyz.com, narinder xyz.com, abc@xyz
        var emailPattern = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
        if (!emailPattern.test(trimmedEmail)) {
          return { field: field, label: label, message: "Enter a valid email address." };
        }
      }
    }

    if (type === "number") {
      var numberValue = Number(rawValue);
      if (rawValue !== "" && isNaN(numberValue)) {
        return { field: field, label: label, message: "Enter a valid number." };
      }
    }

    if (type === "date" || name.indexOf("date") !== -1) {
      var parsed = new Date(rawValue);
      if (isNaN(parsed.getTime())) {
        return { field: field, label: label, message: "Enter a valid date." };
      }
    }

    return null;
  }

  function validateModal(modal) {
    var form = modal.querySelector("form.component-form");
    if (!form) return [];
    var fields = form.querySelectorAll("input, select, textarea");
    var errors = [];
    var radioCache = {};

    toArray(fields).forEach(function (field) {
      var type = (field.getAttribute("type") || "").toLowerCase();
      if (type === "radio") {
        var radioError = validateRadioGroup(form, field, radioCache);
        if (radioError) {
          setFieldError(field, radioError.message);
          errors.push(radioError);
        } else {
          clearFieldError(field);
        }
        return;
      }

      var result = validateField(field, form);
      if (result && result.message) {
        setFieldError(field, result.message);
        errors.push(result);
      } else {
        clearFieldError(field);
      }
    });

    renderSummary(modal, errors);
    return errors;
  }

  function attachForm(form) {
    var modal = form.closest(".component-modal");
    if (!modal) return;

    form.addEventListener("submit", function (event) {
      var errors = validateModal(modal);
      if (errors.length) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
  }

  onReady(function () {
    var modals = document.querySelectorAll(".component-modal");
    if (!modals.length) return;

    document.querySelectorAll(".component-modal form.component-form").forEach(attachForm);

    document.querySelectorAll("[data-modal-open]").forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var id = trigger.getAttribute("data-modal-open");
        if (!id) return;
        var modal = document.getElementById(id);
        if (modal) {
          clearModalValidation(modal);
        }
      });
    });

    modals.forEach(function (modal) {
      modal.addEventListener("click", function (event) {
        if (event.target === modal) {
          clearModalValidation(modal);
        }
      });
      modal.querySelectorAll("[data-modal-close]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          clearModalValidation(modal);
        });
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        document.querySelectorAll(".component-modal.is-open").forEach(function (openModal) {
          clearModalValidation(openModal);
        });
      }
    });
  });
})();
