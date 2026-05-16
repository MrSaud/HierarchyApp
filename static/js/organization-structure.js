/**
 * Organization structure: search, collapse units, jump to tree.
 */
(function () {
  const page = document.getElementById("org-structure-page");
  if (!page) {
    return;
  }

  const searchInput = document.getElementById("org-unit-search");
  const picker = document.getElementById("org-unit-picker");
  const hint = document.getElementById("org-unit-search-hint");
  const emptyMsg = document.getElementById("org-unit-search-empty");
  const expandAllBtn = document.getElementById("org-expand-all");
  const collapseAllBtn = document.getElementById("org-collapse-all");
  const searchPanel = document.getElementById("org-unit-search-panel");
  const searchToggle = document.getElementById("org-unit-search-toggle");
  const units = page.querySelectorAll(".d365-org-unit[data-unit-id]");

  function setSearchPanelExpanded(expanded) {
    if (!searchPanel) {
      return;
    }
    searchPanel.classList.toggle("is-collapsed", !expanded);
    searchPanel.classList.toggle("is-expanded", expanded);
    if (searchToggle) {
      searchToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      searchToggle.title = expanded ? "Collapse find unit" : "Expand find unit";
    }
  }

  if (searchToggle) {
    searchToggle.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      setSearchPanelExpanded(searchPanel.classList.contains("is-collapsed"));
    });
  }

  const searchHead = searchPanel && searchPanel.querySelector(".d365-org-sidebar__head");
  if (searchHead) {
    searchHead.addEventListener("click", function (e) {
      if (e.target.closest(".d365-org-sidebar__toggle")) {
        return;
      }
      setSearchPanelExpanded(searchPanel.classList.contains("is-collapsed"));
    });
  }

  function collapsibleUnits() {
    return page.querySelectorAll(".d365-org-unit.is-collapsed, .d365-org-unit.is-expanded");
  }

  function setExpanded(unit, expanded) {
    const toggle = unit.querySelector(".d365-org-unit__toggle");
    if (expanded) {
      unit.classList.remove("is-collapsed");
      unit.classList.add("is-expanded");
    } else {
      unit.classList.add("is-collapsed");
      unit.classList.remove("is-expanded");
    }
    if (toggle) {
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggle.title = expanded ? "Collapse unit" : "Expand unit";
    }
  }

  function expandUnitAndAncestors(el) {
    let node = el;
    while (node) {
      if (node.classList && node.classList.contains("d365-org-unit")) {
        if (
          node.classList.contains("is-collapsed") ||
          node.classList.contains("is-expanded")
        ) {
          setExpanded(node, true);
        }
      }
      node = node.parentElement;
    }
  }

  function expandAll() {
    collapsibleUnits().forEach((u) => setExpanded(u, true));
  }

  function collapseAll() {
    collapsibleUnits().forEach((u) => setExpanded(u, false));
  }

  page.addEventListener("click", function (e) {
    const toggle = e.target.closest(".d365-org-unit__toggle");
    if (toggle) {
      e.preventDefault();
      const unit = toggle.closest(".d365-org-unit");
      if (unit) {
        const open = unit.classList.contains("is-collapsed");
        setExpanded(unit, open);
      }
      return;
    }

    const head = e.target.closest(".d365-org-unit__head");
    if (head && !e.target.closest("a")) {
      const unit = head.closest(".d365-org-unit");
      const btn = unit && unit.querySelector(".d365-org-unit__toggle");
      if (btn) {
        btn.click();
      }
    }
  });

  if (expandAllBtn) {
    expandAllBtn.addEventListener("click", expandAll);
  }
  if (collapseAllBtn) {
    collapseAllBtn.addEventListener("click", collapseAll);
  }

  function norm(s) {
    return (s || "").toLowerCase().trim();
  }

  function applyFilter() {
    if (!searchInput || !picker) {
      return;
    }
    const q = norm(searchInput.value);
    const pickerBtns = picker.querySelectorAll(".d365-org-unit-picker__btn");
    let visiblePicker = 0;

    pickerBtns.forEach((btn) => {
      const text = norm(btn.getAttribute("data-search"));
      const show = !q || text.includes(q);
      btn.hidden = !show;
      if (show) {
        visiblePicker += 1;
      }
    });

    units.forEach((el) => {
      const text = norm(el.getAttribute("data-search"));
      const match = !q || text.includes(q);
      el.classList.toggle("is-filter-hidden", q.length > 0 && !match);
    });

    if (hint) {
      hint.textContent = q
        ? `${visiblePicker} of ${pickerBtns.length} unit(s)`
        : `${pickerBtns.length} unit(s)`;
    }
    if (emptyMsg) {
      emptyMsg.hidden = visiblePicker > 0;
    }
  }

  function highlightUnit(id) {
    units.forEach((el) => {
      el.classList.toggle("is-highlight", el.getAttribute("data-unit-id") === String(id));
    });
    if (picker) {
      picker.querySelectorAll(".d365-org-unit-picker__btn").forEach((btn) => {
        const on = btn.getAttribute("data-unit-id") === String(id);
        btn.classList.toggle("is-active", on);
        if (on) {
          btn.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      });
    }
  }

  function goToUnit(id) {
    const el = document.getElementById("org-unit-" + id);
    if (!el) {
      return;
    }
    if (el.classList.contains("is-filter-hidden")) {
      if (searchInput) {
        searchInput.value = "";
        applyFilter();
      }
    }
    expandUnitAndAncestors(el);
    highlightUnit(id);
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (searchInput) {
    searchInput.addEventListener("input", applyFilter);
  }

  if (picker) {
    picker.addEventListener("click", function (e) {
      const btn = e.target.closest(".d365-org-unit-picker__btn");
      if (!btn || btn.hidden) {
        return;
      }
      const id = btn.getAttribute("data-unit-id");
      if (id) {
        goToUnit(id);
      }
    });
    applyFilter();
  }

  const hash = window.location.hash;
  if (hash && hash.startsWith("#org-unit-")) {
    const id = hash.slice("#org-unit-".length).trim();
    if (id && /^\d+$/.test(id)) {
      setSearchPanelExpanded(true);
      goToUnit(id);
    }
  }
})();
