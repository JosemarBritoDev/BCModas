(function () {
  "use strict";

  function normalize(value) {
    var hex = (value || "").trim();
    if (!hex) return "";
    if (hex.charAt(0) !== "#") hex = "#" + hex;
    if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(hex)) return hex;
    return "";
  }

  function paint(input) {
    var row = input.closest("tr") || input.closest("fieldset") || input.parentElement;
    var preview = row ? row.querySelector("[data-hex-preview]") : null;
    if (!preview) return;
    var hex = normalize(input.value);
    if (hex) {
      preview.style.background = hex;
      preview.textContent = hex.toUpperCase();
    } else {
      preview.style.background = "#ffffff";
      preview.textContent = "—";
    }
  }

  function bind() {
    document
      .querySelectorAll('input[id$="cor_hex"], input[name$="cor_hex"]')
      .forEach(function (input) {
        if (input.dataset.hexBound === "1") return;
        input.dataset.hexBound = "1";
        input.addEventListener("input", function () {
          paint(input);
        });
        paint(input);
      });
  }

  document.addEventListener("DOMContentLoaded", bind);
  document.addEventListener("formset:added", bind);
  document.addEventListener("unfold:init", bind);
  window.bindHexPreviews = bind;
})();
