// Progressive enhancement only — every page works with JS disabled.

// ── FLASH MESSAGES ──
function dismissFlash(el) {
  if (!el) return;
  el.style.transition = "opacity .2s, transform .2s";
  el.style.opacity = "0";
  el.style.transform = "translateX(6px)";
  setTimeout(function () { el.remove(); }, 200);
}

// ── ADMIN SIDEBAR (mobile drawer) ──
function openSb() {
  var sb = document.getElementById("sidebar");
  var ov = document.getElementById("sb-overlay");
  if (sb) sb.classList.add("open");
  if (ov) ov.style.display = "block";
}

function closeSb() {
  var sb = document.getElementById("sidebar");
  var ov = document.getElementById("sb-overlay");
  if (sb) sb.classList.remove("open");
  if (ov) ov.style.display = "none";
}

document.addEventListener("DOMContentLoaded", function () {
  setTimeout(function () {
    document.querySelectorAll(".flash-success").forEach(dismissFlash);
  }, 4500);

  // Clamp quantity fields before the browser's own validation kicks in.
  document.querySelectorAll("input[name='quantity'][max]").forEach(function (input) {
    var max = parseInt(input.max, 10);
    if (isNaN(max)) return;
    input.addEventListener("input", function () {
      var value = parseInt(input.value, 10);
      if (!isNaN(value) && value > max) input.value = max;
    });
  });

  // Stop a double tap from submitting the confirmation twice.
  var confirmForm = document.querySelector(".confirm-submit");
  if (confirmForm) {
    confirmForm.form.addEventListener("submit", function () {
      setTimeout(function () {
        confirmForm.disabled = true;
        confirmForm.textContent = "…";
      }, 0);
    });
  }

  initCategories();
  initSearch();
});

// ── COLLAPSIBLE CATEGORIES ──
// Which ones are shut is remembered per browser, so a long list stays
// however the visitor left it.
var CLOSED_KEY = "closedCategories";

function readClosed() {
  try {
    var raw = JSON.parse(localStorage.getItem(CLOSED_KEY));
    return Array.isArray(raw) ? raw : [];
  } catch (e) {
    return [];
  }
}

function initCategories() {
  var blocks = document.querySelectorAll(".cat-block[data-cat]");
  if (!blocks.length) return;
  var closed = readClosed();

  blocks.forEach(function (block) {
    if (closed.indexOf(block.dataset.cat) !== -1) block.open = false;

    block.addEventListener("toggle", function () {
      // Filtering opens categories itself; don't record that as a choice.
      if (document.body.classList.contains("is-filtering")) return;
      var list = readClosed().filter(function (n) { return n !== block.dataset.cat; });
      if (!block.open) list.push(block.dataset.cat);
      try {
        localStorage.setItem(CLOSED_KEY, JSON.stringify(list));
      } catch (e) {
        /* private mode — collapsing still works, it just won't be remembered */
      }
    });
  });
}

// ── LIVE SEARCH ──
function matches(name, query) {
  if (!query) return true;
  // Match on the start of any word, so "s" finds "Sleeping mats" and
  // "Soap", and typing further narrows it down.
  return name.toLowerCase().split(/[\s\-/(),.]+/).some(function (word) {
    return word.indexOf(query) === 0;
  });
}

function initSearch() {
  var bar = document.getElementById("searchbar");
  var input = document.getElementById("item-search");
  if (!bar || !input) return;

  var clear = document.getElementById("search-clear");
  var reset = document.getElementById("search-reset");
  var empty = document.getElementById("no-results");
  var blocks = [].slice.call(document.querySelectorAll(".cat-block[data-cat]"));
  var openBeforeFilter = null;

  function apply() {
    var query = input.value.trim().toLowerCase();
    var filtering = query.length > 0;
    var total = 0;

    if (filtering && openBeforeFilter === null) {
      // Remember how things were, so clearing the box restores them.
      openBeforeFilter = blocks.map(function (b) { return b.open; });
    }
    document.body.classList.toggle("is-filtering", filtering);

    blocks.forEach(function (block, index) {
      var shown = 0;
      block.querySelectorAll(".item").forEach(function (item) {
        var hit = matches(item.dataset.name || "", query);
        item.hidden = !hit;
        if (hit) shown++;
      });

      block.hidden = filtering && shown === 0;
      block.querySelector("[data-cat-count]").textContent = shown;
      if (filtering) {
        block.open = true;
      } else if (openBeforeFilter) {
        block.open = openBeforeFilter[index];
      }
      total += shown;
    });

    if (!filtering) openBeforeFilter = null;
    if (empty) empty.hidden = !(filtering && total === 0);
    if (clear) clear.hidden = !filtering;
  }

  input.addEventListener("input", apply);
  input.addEventListener("search", apply);
  if (clear) {
    clear.addEventListener("click", function () {
      input.value = "";
      apply();
      input.focus();
    });
  }
  if (reset) {
    reset.addEventListener("click", function () {
      input.value = "";
      apply();
      input.focus();
    });
  }
}
