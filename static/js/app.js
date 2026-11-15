// Hotel Paradise — comportamiento común
document.addEventListener("DOMContentLoaded", () => {
  // Mensajes de Django como toasts
  document.querySelectorAll(".toast").forEach((el) => bootstrap.Toast.getOrCreateInstance(el).show());

  // Filas de tabla clicables
  document.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.classList.add("fila-link");
    tr.addEventListener("click", (e) => {
      if (e.target.closest("a, button, form")) return;
      window.location = tr.dataset.href;
    });
  });

  // Modal de confirmación: <button data-confirmar data-url=".." data-titulo=".." data-mensaje=".." data-boton="..">
  const modal = document.getElementById("modalConfirmar");
  if (modal) {
    modal.addEventListener("show.bs.modal", (e) => {
      const b = e.relatedTarget;
      modal.querySelector("form").action = b.dataset.url;
      modal.querySelector("[data-titulo]").textContent = b.dataset.titulo || "¿Confirmas la acción?";
      modal.querySelector("[data-mensaje]").textContent = b.dataset.mensaje || "";
      modal.querySelector("[data-boton]").textContent = b.dataset.boton || "Confirmar";
    });
  }

  // Envío automático de filtros al cambiar un select
  document.querySelectorAll("form[data-autoenvio] select, form[data-autoenvio] input[type=date]").forEach((el) =>
    el.addEventListener("change", () => el.form.requestSubmit())
  );
});
