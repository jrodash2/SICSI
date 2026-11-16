"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const menu = document.querySelector("#menu");
  const navigation = document.querySelector("#navigation");
  const scrim = document.querySelector("#navScrim");
  function setMenu(open) {
    if (!navigation || !menu) return;
    navigation.classList.toggle("open", open);
    menu.setAttribute("aria-expanded", String(open));
    if (scrim) scrim.hidden = !open;
  }
  if (menu) menu.addEventListener("click", () => setMenu(!navigation.classList.contains("open")));
  if (scrim) scrim.addEventListener("click", () => setMenu(false));
  document.addEventListener("keydown", event => { if (event.key === "Escape") setMenu(false); });
  document.querySelectorAll("[data-prevent-double-submit]").forEach(form => {
    form.addEventListener("submit", () => {
      if (!form.checkValidity()) return;
      form.querySelectorAll("button[type='submit'], button:not([type])").forEach(button => {
        button.disabled = true;
        button.textContent = "Procesando…";
      });
    });
  });
});
