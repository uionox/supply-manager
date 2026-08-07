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

  // A rejected claim comes back with its form re-opened — bring it into view.
  var open = document.querySelector("details.claim[open]");
  if (open) {
    open.scrollIntoView({ block: "center" });
  }

  document.querySelectorAll(".claim-form").forEach(function (form) {
    var quantity = form.querySelector("input[name='quantity']");
    var max = quantity ? parseInt(quantity.max, 10) : NaN;

    // Clamp before the browser's own validation kicks in.
    if (quantity && !isNaN(max)) {
      quantity.addEventListener("input", function () {
        var value = parseInt(quantity.value, 10);
        if (!isNaN(value) && value > max) quantity.value = max;
      });
    }

    // Stop a double tap from creating two claims.
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type='submit']");
      if (!button) return;
      setTimeout(function () {
        button.disabled = true;
        button.textContent = "Sending…";
      }, 0);
    });
  });
});
