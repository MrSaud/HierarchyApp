/**
 * Multipart upload progress for bulk signature form (XHR + upload progress events).
 */
(function () {
  function init() {
    var form = document.getElementById("bulk-signature-form");
    if (!form || !window.XMLHttpRequest) return;

    var fileInput = document.getElementById("id_bulk_signature_files");
    var wrap = document.getElementById("bulk-upload-progress-wrap");
    var bar = document.getElementById("bulk-upload-progress-bar");
    var pctEl = document.getElementById("bulk-upload-progress-pct");
    var submitBtn = form.querySelector('button[type="submit"]');

    if (!wrap || !bar || !pctEl || !fileInput || !submitBtn) return;

    form.addEventListener("submit", function (e) {
      var files = fileInput.files;
      if (!files || !files.length) return;

      e.preventDefault();

      var xhr = new XMLHttpRequest();
      var fd = new FormData(form);

      wrap.hidden = false;
      bar.value = 0;
      pctEl.textContent = "0%";
      submitBtn.disabled = true;
      form.setAttribute("aria-busy", "true");

      xhr.upload.addEventListener("progress", function (ev) {
        if (ev.lengthComputable && ev.total > 0) {
          var pct = Math.round((ev.loaded / ev.total) * 100);
          bar.value = pct;
          pctEl.textContent = pct + "%";
          bar.setAttribute("aria-valuenow", String(pct));
        } else {
          pctEl.textContent = "Uploading…";
        }
      });

      xhr.addEventListener("load", function () {
        submitBtn.disabled = false;
        form.removeAttribute("aria-busy");

        if (xhr.status >= 200 && xhr.status < 400) {
          window.location.href = xhr.responseURL || form.action || window.location.pathname;
          return;
        }

        wrap.hidden = true;
        bar.value = 0;
        pctEl.textContent = "0%";
        alert("Upload failed (HTTP " + xhr.status + ").");
      });

      xhr.addEventListener("error", function () {
        submitBtn.disabled = false;
        form.removeAttribute("aria-busy");
        wrap.hidden = true;
        bar.value = 0;
        pctEl.textContent = "0%";
        alert("Network error during upload.");
      });

      xhr.addEventListener("abort", function () {
        submitBtn.disabled = false;
        form.removeAttribute("aria-busy");
      });

      var url = form.getAttribute("action") || window.location.pathname;
      xhr.open("POST", url);
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      var csrf = fd.get("csrfmiddlewaretoken");
      if (csrf) {
        xhr.setRequestHeader("X-CSRFToken", csrf);
      }
      xhr.send(fd);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
