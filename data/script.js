/**
 * Section toggles
 */
function _setToggleState(id, show) {
  var el = document.getElementById(id);
  if (!el) return;

  el.style.display = show ? "block" : "none";

  var btn = document.querySelector('[data-toggle-target="' + id + '"]');
  if (btn) {
    btn.setAttribute("aria-expanded", show ? "true" : "false");
    btn.classList.toggle("toggle-open", !!show);
  }
}

function hideButton(id) {
  var x = document.getElementById(id);
  if (!x) return;

  var current = window.getComputedStyle(x).display;
  _setToggleState(id, current === "none");
}

/**
 * Legacy visibility helpers
 */
function showAll(ids) {
  if (!ids) return;
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = "block";
  });
}

function hideAll(ids) {
  if (!ids) return;
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = "none";
  });
}

function defaultAll(shown, hidden) {
  showAll(shown);
  hideAll(hidden);
}

function showAllToggles() {
  document.querySelectorAll(".toggle-block").forEach(function(el) {
    el.style.display = "block";
  });
}

function hideAllToggles() {
  document.querySelectorAll(".toggle-block").forEach(function(el) {
    el.style.display = "none";
  });
}

function defaultToggles() {
  document.querySelectorAll(".toggle-block").forEach(function(el) {
    var def = (el.getAttribute("data-default") || "show").toLowerCase();
    el.style.display = (def === "hide") ? "none" : "block";
  });
}

/**
 * Back-to-top button
 */
window.onscroll = showHideScrollButton;

function showHideScrollButton() {
  var topButton = document.getElementById("topButton");
  if (!topButton) return;
  topButton.style.display =
    (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) ? "block" : "none";
}

function backToTop() {
  document.body.scrollTop = 0;
  document.documentElement.scrollTop = 0;
}

/**
 * Gallery
 */
function displayImage(imgs, expandedImageID, imageTextID) {
  var expandImg = document.getElementById(expandedImageID);
  var imgText = document.getElementById(imageTextID);
  if (!expandImg || !imgText) return;

  expandImg.src = imgs.src;
  imgText.innerHTML = imgs.alt;
  if (expandImg.parentElement) expandImg.parentElement.style.display = "block";
}

/**
 * Radar controls
 */
function toggleRadarScale(containerId) {
  var host = document.getElementById(containerId);
  if (!host) return;

  var normal = host.querySelector('[data-scale="normal"]');
  var log = host.querySelector('[data-scale="log"]');
  if (!normal || !log) return;

  var btn = host.querySelector('[data-radar-toggle="scale"]');

  var showLog = log.hasAttribute("hidden");
  if (showLog) {
    log.removeAttribute("hidden");
    normal.setAttribute("hidden", "");
  } else {
    normal.removeAttribute("hidden");
    log.setAttribute("hidden", "");
  }

  if (btn) btn.textContent = showLog ? "Scale: log" : "Scale: normal";
}

/**
 * Global module filter (all / issues / errors)
 */
function setGlobalFilter(mode) {
  mode = (mode || "all").toLowerCase();

  document.querySelectorAll(".module-card").forEach(function (card) {
    var hasIssues = (card.getAttribute("data-has-issues") === "1");
    var hasErrors = (card.getAttribute("data-has-errors") === "1");

    var show = true;
    if (mode === "issues") show = hasIssues;
    else if (mode === "errors") show = hasErrors;

    card.style.display = show ? "" : "none";
  });

  ["filterAll", "filterIssues", "filterErrors"].forEach(function (id) {
    var b = document.getElementById(id);
    if (b) b.classList.remove("active");
  });

  var activeId = (mode === "issues") ? "filterIssues" : (mode === "errors") ? "filterErrors" : "filterAll";
  var activeBtn = document.getElementById(activeId);
  if (activeBtn) activeBtn.classList.add("active");
}

document.addEventListener("DOMContentLoaded", function () {
  setGlobalFilter("all");

  document.querySelectorAll(".toggle-block").forEach(function (el) {
    if (!el.id) return;
    var visible = window.getComputedStyle(el).display !== "none";
    var btn = document.querySelector('[data-toggle-target="' + el.id + '"]');
    if (btn) {
      btn.setAttribute("aria-expanded", visible ? "true" : "false");
      btn.classList.toggle("toggle-open", visible);
    }
  });
});

/**
 * Per-table tools for report tables
 */
(function () {
  function normalizeText(s) {
    return (s == null ? "" : String(s)).replace(/\s+/g, " ").trim().toLowerCase();
  }

  function cellText(td) {
    return normalizeText(td ? td.textContent : "");
  }

  function detectComparable(a, b) {
    const clean = (v) => String(v).replace(/\s+/g, "").replace(/,/g, ".");
    const na = parseFloat(clean(a));
    const nb = parseFloat(clean(b));
    const aNum = !Number.isNaN(na) && clean(a).match(/^-?\d+(\.\d+)?/);
    const bNum = !Number.isNaN(nb) && clean(b).match(/^-?\d+(\.\d+)?/);
    return (aNum && bNum) ? { kind: "num", na, nb } : { kind: "str" };
  }

  function debounce(fn, ms) {
    let t = null;
    return function () {
      const args = arguments;
      if (t) clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function setPanelOpen(panel, btn, open) {
    panel.classList.toggle("is-open", !!open);
    panel.hidden = !open;
    if (btn) {
      btn.classList.toggle("open", !!open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }
  }

  function isPanelOpen(panel) {
    return panel && (panel.classList.contains("is-open") || panel.hidden === false);
  }

  function enhanceTable(table) {
    if (!table || table.getAttribute("data-enhanced") === "1") return;

    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    if (!thead || !tbody) return;

    const headerRow = thead.querySelector("tr");
    if (!headerRow) return;

    const headerCells = Array.from(headerRow.querySelectorAll("th"));
    if (headerCells.length === 0) return;

    Array.from(tbody.querySelectorAll("tr")).forEach((tr, i) => {
      tr.setAttribute("data-orig-index", String(i));
    });

    const toggleHost = table.closest(".toggle-block");
    const insertTarget = table.closest(".table-container") || table;
    const host = toggleHost || insertTarget.parentElement;
    if (!host) return;

    if (insertTarget.previousElementSibling && insertTarget.previousElementSibling.classList
        && insertTarget.previousElementSibling.classList.contains("table-tools-panel")) {
      table.setAttribute("data-enhanced", "1");
      return;
    }

    const toolsBar = document.createElement("div");
    toolsBar.className = "table-toolsbar";

    const toolsBtn = document.createElement("button");
    toolsBtn.type = "button";
    toolsBtn.className = "table-tools-btn";
    toolsBtn.textContent = "Table tools";
    toolsBtn.setAttribute("aria-expanded", "false");

    const statusPill = document.createElement("span");
    statusPill.className = "table-status-pill";
    statusPill.textContent = "";

    toolsBar.appendChild(toolsBtn);
    toolsBar.appendChild(statusPill);

    const panel = document.createElement("div");
    panel.className = "table-tools-panel";
    panel.hidden = true;

    const row1 = document.createElement("div");
    row1.className = "table-tools-row";

    const search = document.createElement("input");
    search.type = "search";
    search.className = "table-search";
    search.placeholder = "Search this table…";

    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "table-clear";
    clearBtn.textContent = "Clear";

    row1.appendChild(search);
    row1.appendChild(clearBtn);

    const hint = document.createElement("div");
    hint.className = "table-tools-hint";
    hint.textContent = "Column filters (all must match):";

    const grid = document.createElement("div");
    grid.className = "table-filters-grid";

    const filterInputs = headerCells.map((th, idx) => {
      const cell = document.createElement("div");
      cell.className = "table-filter-cell";

      const lab = document.createElement("label");
      lab.className = "table-filter-label";
      lab.textContent = (th.textContent || ("Col " + (idx + 1))).trim();

      const inp = document.createElement("input");
      inp.type = "text";
      inp.className = "table-filter";
      inp.placeholder = "Filter…";
      inp.setAttribute("data-col", String(idx));

      cell.appendChild(lab);
      cell.appendChild(inp);
      grid.appendChild(cell);
      return inp;
    });

    panel.appendChild(row1);
    panel.appendChild(hint);
    panel.appendChild(grid);

    host.insertBefore(toolsBar, insertTarget);
    host.insertBefore(panel, insertTarget);

    let sortCol = -1;
    let sortDir = 0;

    function updateSortIndicators() {
      headerCells.forEach((th, i) => {
        th.classList.remove("sort-asc", "sort-desc");
        if (i === sortCol) {
          if (sortDir === 1) th.classList.add("sort-asc");
          else if (sortDir === -1) th.classList.add("sort-desc");
        }
      });
    }

    function applyFilters() {
      const q = normalizeText(search.value);
      const colFilters = filterInputs.map((inp) => normalizeText(inp.value));

      const rows = Array.from(tbody.querySelectorAll("tr"));
      let visible = 0;

      rows.forEach((tr) => {
        const tds = Array.from(tr.querySelectorAll("td"));
        const rowText = normalizeText(tr.textContent);

        if (q && !rowText.includes(q)) {
          tr.style.display = "none";
          return;
        }

        for (let i = 0; i < colFilters.length; i++) {
          const f = colFilters[i];
          if (!f) continue;
          const v = cellText(tds[i]);
          if (!v.includes(f)) {
            tr.style.display = "none";
            return;
          }
        }

        tr.style.display = "";
        visible++;
      });

      statusPill.textContent = `Rows: ${visible}/${rows.length}`;
    }

    function restoreOriginalOrder() {
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {
        const ia = parseInt(a.getAttribute("data-orig-index") || "0", 10);
        const ib = parseInt(b.getAttribute("data-orig-index") || "0", 10);
        return ia - ib;
      });
      rows.forEach((tr) => tbody.appendChild(tr));
    }

    function sortRows() {
      if (sortDir === 0 || sortCol < 0) {
        restoreOriginalOrder();
        sortCol = -1;
        updateSortIndicators();
        applyFilters();
        return;
      }

      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((ra, rb) => {
        const aTds = ra.querySelectorAll("td");
        const bTds = rb.querySelectorAll("td");

        const a = aTds[sortCol] ? aTds[sortCol].textContent.trim() : "";
        const b = bTds[sortCol] ? bTds[sortCol].textContent.trim() : "";

        const cmp = detectComparable(a, b);
        if (cmp.kind === "num") {
          if (cmp.na < cmp.nb) return -1 * sortDir;
          if (cmp.na > cmp.nb) return  1 * sortDir;
          return 0;
        }

        return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }) * sortDir;
      });

      rows.forEach((tr) => tbody.appendChild(tr));
      updateSortIndicators();
      applyFilters();
    }

    headerCells.forEach((th, idx) => {
      th.style.cursor = "pointer";
      th.addEventListener("click", function (ev) {
        const tag = (ev.target && ev.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "button" || tag === "select") return;

        if (sortCol !== idx) {
          sortCol = idx;
          sortDir = 1;
        } else {
          if (sortDir === 1) sortDir = -1;
          else if (sortDir === -1) { sortDir = 0; sortCol = -1; }
          else sortDir = 1;
        }

        sortRows();
      });
    });

    toolsBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      const open = !isPanelOpen(panel);
      setPanelOpen(panel, toolsBtn, open);
      if (open) setTimeout(() => search.focus(), 0);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isPanelOpen(panel)) {
        setPanelOpen(panel, toolsBtn, false);
      }
    });

    document.addEventListener("click", function (ev) {
      if (!isPanelOpen(panel)) return;

      const t = ev.target;
      if (panel.contains(t)) return;
      if (toolsBar.contains(t)) return;
      if (insertTarget.contains(t)) return;

      setPanelOpen(panel, toolsBtn, false);
    });

    const debouncedApply = debounce(applyFilters, 80);
    search.addEventListener("input", debouncedApply);
    filterInputs.forEach((inp) => inp.addEventListener("input", debouncedApply));

    clearBtn.addEventListener("click", function () {
      search.value = "";
      filterInputs.forEach((i) => (i.value = ""));
      applyFilters();
    });

    table.setAttribute("data-enhanced", "1");
    applyFilters();
    updateSortIndicators();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table.report-table").forEach(enhanceTable);
  });
})();
