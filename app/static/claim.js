// Progressive enhancement only — every form here works with JS disabled.

document.addEventListener("DOMContentLoaded", function () {
  // If the server re-rendered the page with a form open (a rejected claim),
  // bring it into view.
  var open = document.querySelector("details.claim[open]");
  if (open) {
    open.scrollIntoView({ block: "center" });
    var firstEmpty = open.querySelector("input:placeholder-shown, input[value='']");
    if (firstEmpty) firstEmpty.focus({ preventScroll: true });
  }

  document.querySelectorAll(".claim__form").forEach(function (form) {
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
