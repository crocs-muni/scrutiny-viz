/**
 * Toggle a single block by id (Show/Hide button)
 */
function hideButton(id) {
  var x = document.getElementById(id);
  if (!x) return;
  if (x.style.display === "none") {
    x.style.display = "block";
  } else {
    x.style.display = "none";
  }
}

/**
 * Legacy helpers (kept for backward compatibility)
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

// Floating button based on https://www.w3schools.com/howto/howto_js_scroll_to_top.asp
window.onscroll = showHideScrollButton;

function showHideScrollButton() {
  var topButton = document.getElementById("topButton");
  if (!topButton) return;
  if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
    topButton.style.display = "block";
  } else {
    topButton.style.display = "none";
  }
}

// Taken from https://www.w3schools.com/howto/howto_js_scroll_to_top.asp
function backToTop() {
  document.body.scrollTop = 0; // For Safari
  document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
}

/* Gallery */

function displayImage(imgs, expandedImageID, imageTextID) {
  var expandImg = document.getElementById(expandedImageID);
  var imgText = document.getElementById(imageTextID);
  if (!expandImg || !imgText) return;

  expandImg.src = imgs.src;
  imgText.innerHTML = imgs.alt;
  if (expandImg.parentElement) {
    expandImg.parentElement.style.display = "block";
  }
}

/* Gallery end */

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

  if (btn) {
    btn.textContent = showLog ? "Scale: log" : "Scale: normal";
  }
}

