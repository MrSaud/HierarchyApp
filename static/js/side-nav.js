/**
 * Side navigation: mobile overlay drawer; desktop collapsed icon rail by default.
 */
(function () {
  const host = document.getElementById("d365-nav-host");
  const fab = document.getElementById("d365-nav-fab");
  const backdrop = document.getElementById("d365-nav-backdrop");
  const collapseToggle = document.getElementById("d365-nav-collapse-toggle");

  if (!host || !fab) {
    return;
  }

  const mobileMq = window.matchMedia("(max-width: 768px)");
  const desktopMq = window.matchMedia("(min-width: 769px)");
  const NAV_COLLAPSED_KEY = "d365-nav-collapsed";

  function setOpen(open) {
    host.classList.toggle("is-open", open);
    fab.setAttribute("aria-expanded", open ? "true" : "false");
    fab.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    if (backdrop) {
      if (open) {
        backdrop.removeAttribute("hidden");
      } else {
        backdrop.setAttribute("hidden", "");
      }
    }
    document.body.classList.toggle("d365-nav-is-open", open);
  }

  function close() {
    setOpen(false);
  }

  function toggle() {
    setOpen(!host.classList.contains("is-open"));
  }

  function setNavCollapsed(collapsed) {
    if (!desktopMq.matches) {
      return;
    }
    host.classList.toggle("is-collapsed", collapsed);
    host.classList.toggle("is-expanded", !collapsed);
    if (collapseToggle) {
      collapseToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      collapseToggle.title = collapsed ? "Expand menu" : "Collapse menu";
    }
    try {
      localStorage.setItem(NAV_COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch (_err) {
      /* ignore */
    }
  }

  function initDesktopCollapse() {
    if (!desktopMq.matches) {
      host.classList.remove("is-collapsed", "is-expanded");
      return;
    }
    let collapsed = true;
    try {
      const stored = localStorage.getItem(NAV_COLLAPSED_KEY);
      if (stored !== null) {
        collapsed = stored === "1";
      }
    } catch (_err) {
      /* ignore */
    }
    setNavCollapsed(collapsed);
  }

  fab.addEventListener("click", function () {
    if (!mobileMq.matches) {
      return;
    }
    toggle();
  });

  backdrop?.addEventListener("click", close);

  mobileMq.addEventListener("change", function (e) {
    if (!e.matches) {
      close();
    }
    initDesktopCollapse();
  });

  desktopMq.addEventListener("change", initDesktopCollapse);

  collapseToggle?.addEventListener("click", function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (!desktopMq.matches) {
      return;
    }
    setNavCollapsed(!host.classList.contains("is-collapsed"));
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && mobileMq.matches) {
      close();
    }
  });

  initDesktopCollapse();
})();
