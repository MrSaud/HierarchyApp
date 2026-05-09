/**
 * Makes <select> elements searchable via Tom Select (loaded before this script).
 * - Main UI: all select.d365-select
 * - Django admin: #content-main select, excluding filter_horizontal / filter_vertical widgets
 */
(function () {
  var TS = typeof TomSelect !== "undefined" ? TomSelect : null;

  function defaults(el, adminMode) {
    var useBody = !!adminMode || !!el.closest(".d365-app-bar");
    return {
      allowEmptyOption: true,
      create: false,
      maxOptions: null,
      hideSelected: false,
      sortField: { field: "$order", direction: "asc" },
      dropdownParent: useBody ? document.body : null,
    };
  }

  function skipSearchableEnhancement(el) {
    return el.getAttribute("data-no-searchable-select") === "1";
  }

  function initOne(el, adminMode) {
    if (!TS || el.tomselect) return;
    if (skipSearchableEnhancement(el)) return;
    if (el.closest(".selector")) return;

    var opts = defaults(el, adminMode);
    try {
      new TS(el, opts);
    } catch (e) {
      console.warn("Tom Select init failed", el.id || el.name, e);
    }
  }

  function initMainUi() {
    if (!TS) return;
    document.querySelectorAll("select.d365-select").forEach(function (el) {
      initOne(el, false);
    });
  }

  function initAdminUi() {
    if (!TS) return;
    var root = document.getElementById("content-main");
    if (!root) return;
    root.querySelectorAll("select").forEach(function (el) {
      initOne(el, true);
    });
  }

  function run() {
    initMainUi();
    initAdminUi();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
