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
        confirmForm.textContent = "Confirming…";
      }, 0);
    });
  }
});
