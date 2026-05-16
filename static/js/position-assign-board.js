/**
 * Drag-and-drop position assignment board with Assign / Remove buttons.
 */
(function () {
  const root = document.getElementById("position-assign-board");
  if (!root || !window.fetch) {
    return;
  }

  const csrfInput = root.querySelector("[name=csrfmiddlewaretoken]");
  const assignUrl = root.dataset.assignUrl;
  const unassignUrl = root.dataset.unassignUrl;
  const positionUrlTemplate = root.dataset.positionUrlTemplate;

  let employees = [];
  const employeesScript = document.getElementById("board-employees-data");
  if (employeesScript) {
    try {
      employees = JSON.parse(employeesScript.textContent || "[]");
    } catch (e) {
      employees = [];
    }
  }

  const positionButtons = root.querySelectorAll(".d365-assign-board__position-btn");
  const poolZone = document.getElementById("assign-board-pool");
  const targetZone = document.getElementById("assign-board-target");
  const poolList = document.getElementById("assign-board-pool-list");
  const targetList = document.getElementById("assign-board-target-list");
  const poolHint = document.getElementById("assign-board-pool-hint");
  const targetHint = document.getElementById("assign-board-target-hint");
  const positionLabel = document.getElementById("assign-board-position-label");
  const positionMeta = document.getElementById("assign-board-position-meta");
  const statusEl = document.getElementById("assign-board-status");
  const searchInput = document.getElementById("assign-board-search");
  const primaryCheckbox = document.getElementById("assign-board-primary");

  if (
    !csrfInput ||
    !poolZone ||
    !targetZone ||
    !poolList ||
    !targetList ||
    !positionLabel
  ) {
    return;
  }

  let selectedPositionId = null;
  let assignments = [];
  let searchQuery = "";
  let busy = false;

  function getCsrfToken() {
    return csrfInput.value;
  }

  function positionDataUrl(id) {
    return positionUrlTemplate.replace("__ID__", String(id));
  }

  function setStatus(msg, isError) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("d365-assign-board__status--error", Boolean(isError));
  }

  function isAssignedToSelectedPosition(employeeId) {
    return assignments.some(
      (a) => Number(a.employee_id) === Number(employeeId),
    );
  }

  function matchesSearch(label, username) {
    if (!searchQuery) {
      return true;
    }
    const q = searchQuery.toLowerCase();
    return (
      (label && label.toLowerCase().includes(q)) ||
      (username && username.toLowerCase().includes(q))
    );
  }

  function makeActionButton(label, className, title) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = className;
    btn.textContent = label;
    if (title) {
      btn.title = title;
    }
    return btn;
  }

  function assignAsPrimary() {
    return !primaryCheckbox || primaryCheckbox.checked;
  }

  function makeChip(opts) {
    const li = document.createElement("li");
    const chip = document.createElement("div");
    chip.className = "d365-assign-board__chip";
    chip.draggable = true;
    chip.setAttribute("role", "listitem");
    chip.dataset.employeeId = String(opts.employeeId);
    chip.dataset.label = opts.label;

    if (opts.assignmentId && typeof opts.isPrimary === "boolean") {
      const badge = document.createElement("span");
      badge.className = opts.isPrimary
        ? "d365-assign-board__chip-badge"
        : "d365-assign-board__chip-badge d365-assign-board__chip-badge--secondary";
      badge.textContent = opts.isPrimary ? "Primary" : "Secondary";
      chip.appendChild(badge);
    }

    const labelEl = document.createElement("span");
    labelEl.className = "d365-assign-board__chip-label";
    labelEl.textContent = opts.label;
    chip.appendChild(labelEl);

    const actions = document.createElement("div");
    actions.className = "d365-assign-board__chip-actions";

    if (opts.assignmentId) {
      chip.dataset.assignmentId = String(opts.assignmentId);
      chip.dataset.fromZone = "target";
      const removeBtn = makeActionButton(
        "Remove",
        "d365-btn d365-btn--compact d365-assign-board__chip-btn d365-assign-board__chip-btn--remove",
        "Remove from this position",
      );
      removeBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
        if (!busy) {
          unassign(opts.assignmentId);
        }
      });
      actions.appendChild(removeBtn);
    } else {
      chip.dataset.fromZone = "pool";
      const assignBtn = makeActionButton(
        "Assign",
        "d365-btn d365-btn--compact d365-assign-board__chip-btn",
        "Assign to selected position",
      );
      assignBtn.disabled = !selectedPositionId;
      assignBtn.addEventListener("click", (evt) => {
        evt.preventDefault();
        evt.stopPropagation();
        if (!busy && selectedPositionId) {
          assignEmployee(opts.employeeId);
        }
      });
      actions.appendChild(assignBtn);
    }

    chip.appendChild(actions);
    li.appendChild(chip);
    return li;
  }

  function renderLists() {
    poolList.innerHTML = "";
    targetList.innerHTML = "";

    let poolCount = 0;
    employees.forEach((emp) => {
      if (isAssignedToSelectedPosition(emp.id)) {
        return;
      }
      if (!matchesSearch(emp.label, emp.username)) {
        return;
      }
      poolList.appendChild(
        makeChip({
          employeeId: emp.id,
          label: emp.label,
        }),
      );
      poolCount += 1;
    });

    assignments.forEach((a) => {
      if (!matchesSearch(a.label, "")) {
        return;
      }
      targetList.appendChild(
        makeChip({
          employeeId: a.employee_id,
          assignmentId: a.id,
          label: a.label,
          isPrimary: Boolean(a.is_primary),
        }),
      );
    });

    const targetCount = targetList.children.length;

    poolList.hidden = poolCount === 0;
    targetList.hidden = targetCount === 0;

    if (selectedPositionId) {
      poolHint.hidden = poolCount > 0;
      poolHint.textContent =
        poolCount === 0
          ? searchQuery
            ? "No matching employees available for this position."
            : "Everyone is already assigned to this position."
          : "Drag to the assigned column or click Assign →";

      targetHint.hidden = targetCount > 0;
      targetHint.textContent =
        targetCount === 0
          ? "Drop employees here to assign them to this position."
          : "Drag back to unassign or click Remove.";
    } else {
      poolHint.hidden = false;
      poolHint.textContent = "Select a position to see who can be assigned.";
      targetHint.hidden = false;
      targetHint.textContent = "Select a position on the left, then assign employees.";
    }
  }

  function setSelectedPosition(id) {
    selectedPositionId = id;
    positionButtons.forEach((btn) => {
      const active = Number(btn.dataset.positionId) === id;
      btn.classList.toggle("is-selected", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    if (!id) {
      positionLabel.textContent = "—";
      if (positionMeta) {
        positionMeta.textContent = "";
      }
      targetZone.classList.add("d365-assign-board__dropzone--disabled");
      targetZone.setAttribute("aria-disabled", "true");
      poolZone.classList.add("d365-assign-board__dropzone--disabled");
      assignments = [];
      renderLists();
      return;
    }

    targetZone.classList.remove("d365-assign-board__dropzone--disabled");
    targetZone.setAttribute("aria-disabled", "false");
    poolZone.classList.remove("d365-assign-board__dropzone--disabled");

    const activeBtn = root.querySelector(
      `.d365-assign-board__position-btn[data-position-id="${id}"]`,
    );
    if (activeBtn) {
      positionLabel.textContent = activeBtn.dataset.positionTitle || "Position";
    }

    const url = new URL(window.location.href);
    url.searchParams.set("position", String(id));
    window.history.replaceState({}, "", url);

    renderLists();
    loadPosition(id);
  }

  async function loadPosition(id) {
    setStatus("Loading assignments…", false);
    busy = true;
    try {
      const resp = await fetch(positionDataUrl(id), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "Could not load position.");
      }
      assignments = Array.isArray(data.assignments) ? data.assignments : [];
      const pos = data.position || {};
      if (positionMeta) {
        const parts = [];
        if (pos.ou_name) {
          parts.push(pos.ou_name);
        }
        if (pos.code) {
          parts.push(pos.code);
        }
        if (!pos.is_active) {
          parts.push("Inactive");
        }
        positionMeta.textContent = parts.join(" · ");
      }
      renderLists();
      setStatus("", false);
    } catch (err) {
      assignments = [];
      renderLists();
      setStatus(err.message || "Load failed.", true);
    } finally {
      busy = false;
      renderLists();
    }
  }

  async function apiPost(url, body) {
    const resp = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    return { resp, data };
  }

  async function assignEmployee(employeeId) {
    if (!selectedPositionId || busy) {
      return;
    }
    busy = true;
    setStatus("Assigning…", false);
    try {
      const { resp, data } = await apiPost(assignUrl, {
        position_id: selectedPositionId,
        employee_id: employeeId,
        is_primary: assignAsPrimary(),
      });
      if (!resp.ok) {
        throw new Error(data.detail || "Assign failed.");
      }
      if (data.assignment) {
        const exists = assignments.some(
          (a) => Number(a.id) === Number(data.assignment.id),
        );
        if (!exists) {
          assignments.push(data.assignment);
        }
      }
      renderLists();
      setStatus(data.detail || "Assigned.", false);
    } catch (err) {
      setStatus(err.message || "Assign failed.", true);
    } finally {
      busy = false;
    }
  }

  async function unassign(assignmentId) {
    if (busy) {
      return;
    }
    busy = true;
    setStatus("Removing…", false);
    try {
      const { resp, data } = await apiPost(unassignUrl, {
        assignment_id: assignmentId,
      });
      if (!resp.ok) {
        throw new Error(data.detail || "Remove failed.");
      }
      assignments = assignments.filter(
        (a) => Number(a.id) !== Number(assignmentId),
      );
      renderLists();
      setStatus("Removed from position.", false);
    } catch (err) {
      setStatus(err.message || "Remove failed.", true);
    } finally {
      busy = false;
    }
  }

  function chipFromEvent(evt) {
    return evt.target.closest(".d365-assign-board__chip");
  }

  let dragPayload = null;

  root.addEventListener("dragstart", (evt) => {
    if (evt.target.closest(".d365-assign-board__chip-btn")) {
      evt.preventDefault();
      return;
    }
    const chip = chipFromEvent(evt);
    if (!chip || busy) {
      evt.preventDefault();
      return;
    }
    dragPayload = {
      employeeId: Number(chip.dataset.employeeId),
      assignmentId: chip.dataset.assignmentId
        ? Number(chip.dataset.assignmentId)
        : null,
      fromZone: chip.dataset.fromZone,
      label: chip.dataset.label,
    };
    chip.classList.add("is-dragging");
    evt.dataTransfer.effectAllowed = "move";
    evt.dataTransfer.setData("text/plain", chip.dataset.label || "");
  });

  root.addEventListener("dragend", () => {
    root.querySelectorAll(".d365-assign-board__chip.is-dragging").forEach((el) => {
      el.classList.remove("is-dragging");
    });
    root
      .querySelectorAll(".d365-assign-board__dropzone.is-drag-over")
      .forEach((el) => el.classList.remove("is-drag-over"));
    dragPayload = null;
  });

  function bindDropZone(zone) {
    zone.addEventListener("dragover", (evt) => {
      if (!dragPayload || busy) {
        return;
      }
      if (zone.classList.contains("d365-assign-board__dropzone--disabled")) {
        return;
      }
      const zoneName = zone.dataset.dropZone;
      if (zoneName === "target" && dragPayload.fromZone === "target") {
        return;
      }
      if (zoneName === "pool" && dragPayload.fromZone === "pool") {
        return;
      }
      evt.preventDefault();
      evt.dataTransfer.dropEffect = "move";
      zone.classList.add("is-drag-over");
    });

    zone.addEventListener("dragleave", (evt) => {
      if (!zone.contains(evt.relatedTarget)) {
        zone.classList.remove("is-drag-over");
      }
    });

    zone.addEventListener("drop", (evt) => {
      evt.preventDefault();
      zone.classList.remove("is-drag-over");
      if (!dragPayload || busy || !selectedPositionId) {
        return;
      }
      const zoneName = zone.dataset.dropZone;
      if (zoneName === "target" && dragPayload.fromZone === "pool") {
        assignEmployee(dragPayload.employeeId);
      } else if (
        zoneName === "pool" &&
        dragPayload.fromZone === "target" &&
        dragPayload.assignmentId
      ) {
        unassign(dragPayload.assignmentId);
      }
    });
  }

  bindDropZone(poolZone);
  bindDropZone(targetZone);

  positionButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.positionId);
      if (id === selectedPositionId) {
        return;
      }
      setSelectedPosition(id);
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      searchQuery = searchInput.value.trim();
      renderLists();
    });
  }

  const initial = root.dataset.selectedPosition;
  if (initial) {
    const id = Number(initial);
    if (id) {
      setSelectedPosition(id);
    }
  } else if (positionButtons.length) {
    setSelectedPosition(Number(positionButtons[0].dataset.positionId));
  } else {
    renderLists();
  }
})();
