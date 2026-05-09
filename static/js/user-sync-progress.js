/**
 * Streaming NDJSON user sync: updates progress bar + percentage while syncing.
 */
(function () {
  const form = document.getElementById("user-sync-form");
  if (!form || !window.fetch || !form.dataset.streamUrl) {
    return;
  }

  const streamUrl = form.dataset.streamUrl;
  const wrap = document.getElementById("user-sync-progress-wrap");
  const bar = document.getElementById("user-sync-progress-bar");
  const pctEl = document.getElementById("user-sync-progress-pct");
  const labelEl = document.getElementById("user-sync-progress-status");
  const resultRoot = document.getElementById("sync-result-root");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]");
  const submitBtn = form.querySelector('button[type="submit"]');

  if (!wrap || !bar || !pctEl || !labelEl || !resultRoot || !csrf || !submitBtn) {
    return;
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function renderResult(ev) {
    const st = ev.stats;
    const errs = st.errors || [];
    let html =
      '<section class="d365-form-section d365-form-section--attached" aria-labelledby="sec-sync-result">';
    html += '<h2 class="d365-form-section__title" id="sec-sync-result">Last run</h2>';
    html += '<ul class="d365-help">';
    html += `<li>Remote rows parsed: ${ev.row_count}</li>`;
    html += `<li>Users created: ${st.created}</li>`;
    html += `<li>Users updated: ${st.updated}</li>`;
    html += `<li>Rows skipped (no recognizable username): ${st.skipped}</li>`;
    html += `<li>Employees linked to tenant (sync): ${st.tenant_linked}</li>`;
    html += `<li>Employee profiles created (were missing): ${st.employees_created}</li>`;
    html += `<li>Employee profiles updated from remote data: ${st.employees_updated}</li>`;
    html += `<li>Manager links resolved: ${st.managers_linked}</li>`;
    html += "</ul>";
    if (errs.length) {
      html += '<p class="d365-help"><strong>Errors:</strong></p><ul class="d365-help">';
      errs.forEach(function (err) {
        html += `<li>${esc(err)}</li>`;
      });
      html += "</ul>";
    }
    html += "</section>";
    resultRoot.innerHTML = html;
  }

  function setProgress(pct, statusText) {
    const n = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
    bar.value = n;
    bar.setAttribute("aria-valuenow", String(n));
    pctEl.textContent = n + "%";
    if (statusText) {
      labelEl.textContent = statusText;
    }
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    submitBtn.disabled = true;
    wrap.hidden = false;
    setProgress(0, "Starting…");

    try {
      const resp = await fetch(streamUrl, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: { "X-CSRFToken": csrf.value },
      });

      if (!resp.ok) {
        let msg = "Sync failed (" + resp.status + ").";
        try {
          const j = await resp.json();
          if (j.detail) {
            msg = j.detail;
          }
        } catch (_) {
          /* ignore */
        }
        setProgress(0, msg);
        return;
      }

      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) {
            continue;
          }
          let ev;
          try {
            ev = JSON.parse(line);
          } catch (_) {
            continue;
          }
          if (ev.phase === "fetch") {
            setProgress(ev.pct, ev.label || "Fetching remote users…");
          } else if (ev.phase === "fetch_done") {
            const t = ev.total != null ? ` (${ev.total} rows)` : "";
            setProgress(ev.pct, (ev.label || "Processing rows…") + t);
          } else if (ev.phase === "row") {
            setProgress(
              ev.pct,
              "Row " + ev.done + " / " + ev.total,
            );
          } else if (ev.phase === "managers") {
            setProgress(ev.pct, ev.label || "Resolving managers…");
          } else if (ev.phase === "complete") {
            setProgress(100, ev.label || "Done");
            renderResult(ev);
          } else if (ev.phase === "error") {
            setProgress(0, ev.message || "Sync error");
            return;
          }
        }
      }
    } catch (err) {
      setProgress(0, err.message || "Network error");
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
