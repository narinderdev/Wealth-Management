(function () {
  function onReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
    el.style.display = hidden ? "none" : "";
  }

  function clearResults(container) {
    if (!container) return;
    var body = container.querySelector("[data-import-summary-body]");
    var status = container.querySelector("[data-import-summary-status]");
    var errors = container.querySelector("[data-import-errors]");
    if (body) body.innerHTML = "";
    if (status) status.textContent = "";
    if (errors) errors.textContent = "";
  }

  function statusBadge(status) {
    var span = document.createElement("span");
    span.className = "import-status-badge";
    if (status === "success") {
      span.classList.add("import-status-success");
    } else if (status === "partial") {
      span.classList.add("import-status-partial");
    } else {
      span.classList.add("import-status-error");
    }
    span.textContent = status;
    return span;
  }

  function normalizeStatus(status) {
    if (!status) return "unknown";
    return String(status).toLowerCase();
  }

  function getCookie(name) {
    if (!document.cookie) return "";
    var cookies = document.cookie.split(";");
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return "";
  }

  function safeParseJson(resp) {
    var contentType = resp.headers.get("content-type") || "";
    if (contentType.indexOf("application/json") !== -1) {
      return resp.json().catch(function () {
        return null;
      });
    }
    return resp.text().then(function (text) {
      var cleaned = String(text || "")
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      return { status: "failed", message: cleaned || "Unexpected response." };
    });
  }

  function renderSummary(container, data) {
    if (!container) return;
    var body = container.querySelector("[data-import-summary-body]");
    var status = container.querySelector("[data-import-summary-status]");
    var errors = container.querySelector("[data-import-errors]");
    if (!body || !status) return;

    var overall = normalizeStatus(data.status || "success");
    status.innerHTML = "";
    status.appendChild(statusBadge(overall));

    (data.summary || []).forEach(function (row) {
      var tr = document.createElement("tr");
      var statusText = row.status || "ok";
      tr.innerHTML =
        "<td>" +
        (row.sheet || "") +
        "</td><td>" +
        (row.imported || 0) +
        "</td><td>" +
        (row.skipped || 0) +
        "</td><td>" +
        statusText +
        "</td>";
      body.appendChild(tr);
    });

    if (data.message) {
      var messageRow = document.createElement("div");
      messageRow.textContent = data.message;
      status.appendChild(messageRow);
    }

    if (errors && data.errors && data.errors.length) {
      errors.textContent = data.errors
        .slice(0, 5)
        .map(function (err) {
          return (err.sheet ? err.sheet + ": " : "") + err.error;
        })
        .join(" | ");
    }
  }

  onReady(function () {
    var form = document.getElementById("excel-import-form");
    if (!form) return;

    var fileInput = form.querySelector('input[type="file"]');
    var clearInput = form.querySelector("#import-clear-existing");
    var confirmInput = form.querySelector("#import-confirm-clear");
    var statusEl = form.querySelector("[data-import-status]");
    var statusText = form.querySelector("[data-import-status-text]");
    var resultsEl = form.querySelector("[data-import-results]");
    var submitBtn = form.querySelector("[data-import-submit]");

    function updateSubmitState() {
      var hasFile = fileInput && fileInput.files && fileInput.files.length;
      var needsConfirm = clearInput && clearInput.checked;
      var confirmOk = !needsConfirm || (confirmInput && confirmInput.checked);
      if (submitBtn) submitBtn.disabled = !(hasFile && confirmOk);
    }

    function resetFormState() {
      if (fileInput) fileInput.value = "";
      if (clearInput) clearInput.checked = false;
      if (confirmInput) {
        confirmInput.checked = false;
        confirmInput.disabled = true;
      }
      setHidden(statusEl, true);
      setHidden(resultsEl, true);
      clearResults(resultsEl);
      if (submitBtn) submitBtn.disabled = true;
    }

    document.querySelectorAll('[data-modal-open="modal-import-excel"]').forEach(function (trigger) {
      trigger.addEventListener("click", resetFormState);
    });

    resetFormState();

    if (fileInput) {
      fileInput.addEventListener("change", updateSubmitState);
    }

    if (clearInput && confirmInput) {
      clearInput.addEventListener("change", function () {
        confirmInput.disabled = !clearInput.checked;
        if (!clearInput.checked) {
          confirmInput.checked = false;
        }
        updateSubmitState();
      });
      confirmInput.addEventListener("change", updateSubmitState);
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!fileInput || !fileInput.files || !fileInput.files.length) {
        alert("Please choose an Excel file to import.");
        return;
      }
      var fileName = fileInput.files[0].name || "";
      if (!fileName.toLowerCase().endsWith(".xlsx")) {
        alert("Only .xlsx files are supported.");
        return;
      }
      if (clearInput && clearInput.checked && confirmInput && !confirmInput.checked) {
        alert("Please confirm clearing existing data.");
        return;
      }

      setHidden(resultsEl, true);
      clearResults(resultsEl);
      if (statusText) statusText.textContent = "Importing...";
      setHidden(statusEl, false);
      if (submitBtn) submitBtn.disabled = true;

      var data = new FormData(form);
      fetch(form.action, {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": getCookie("csrftoken"),
        },
      })
        .then(function (resp) {
          return safeParseJson(resp).then(function (json) {
            return { status: resp.status, body: json };
          });
        })
        .then(function (payload) {
          setHidden(statusEl, true);
          if (submitBtn) submitBtn.disabled = false;
          var body = payload.body || {};
          if (payload.status >= 400) {
            body.status = body.status || "failed";
            body.errors = body.errors || [{ sheet: "", error: body.message || "Import failed." }];
          }
          renderSummary(resultsEl, body);
          setHidden(resultsEl, false);
          if (body.status === "success") {
            var modal = form.closest(".component-modal");
            setTimeout(function () {
              if (modal) {
                modal.classList.remove("is-open");
                modal.setAttribute("aria-hidden", "true");
              }
              resetFormState();
              window.location.reload();
            }, 800);
          }
        })
        .catch(function () {
          setHidden(statusEl, true);
          if (submitBtn) submitBtn.disabled = false;
          alert("Import failed. Please try again.");
        });
    });
  });
})();
