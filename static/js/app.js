"use strict";
document.addEventListener("DOMContentLoaded", () => {
  const menu = document.querySelector("#menu");
  const navigation = document.querySelector("#navigation");
  if (menu && navigation) menu.addEventListener("click", () => {
    const open = navigation.classList.toggle("open");
    menu.setAttribute("aria-expanded", String(open));
  });
  document.querySelectorAll("[data-prevent-double-submit]").forEach(form => {
    form.addEventListener("submit", () => {
      if (!form.checkValidity()) return;
      form.querySelectorAll("button[type='submit'], button:not([type])").forEach(button => {
        button.disabled = true;
        button.textContent = "Guardando…";
      });
    });
  });
});
