(() => {
  document.querySelectorAll("[data-confirm-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const name = form.dataset.confirmDelete || "este registro";
      if (!window.confirm(`¿Eliminar permanentemente el registro de ${name}?`)) {
        event.preventDefault();
      }
    });
  });
})();
