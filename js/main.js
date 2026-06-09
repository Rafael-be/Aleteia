document.addEventListener("DOMContentLoaded", () => {
  document.body.style.visibility = "visible";
  document.body.style.opacity = "1";

  const token = localStorage.getItem("token");
  const estaLogado = !!token;

  const btnConta = document.getElementById("btnConta");
  const fotoConta = document.getElementById("fotoConta");
  const overlay = document.getElementById("popupOverlay");
  const popup = document.getElementById("popupConta");
  const btnVoltar = document.getElementById("btnVoltar");
  const btnSair = document.getElementById("btnSair");

  function abrirPopupConta() {
    if (overlay) overlay.classList.add("active");
    if (popup) popup.classList.add("active");
  }

  function fecharPopup() {
    if (overlay) overlay.classList.remove("active");
    if (popup) popup.classList.remove("active");
  }

  if (btnConta) {
    if (estaLogado) {
      if (fotoConta) fotoConta.style.display = "block";
      btnConta.addEventListener("click", abrirPopupConta);
    } else {
      btnConta.addEventListener("click", () => {
        window.location.href = "/cadastro";
      });
    }
  }

  if (overlay) overlay.addEventListener("click", fecharPopup);
  if (btnVoltar) btnVoltar.addEventListener("click", fecharPopup);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") fecharPopup();
  });

  if (btnSair) {
    btnSair.addEventListener("click", () => {
      localStorage.removeItem("token");
      window.location.href = "/login";
    });
  }

  const btnMenu = document.getElementById("btnMenuMobile");
  const drawerOverlay = document.getElementById("drawerOverlay");
  const sidebarDrawer = document.querySelector(".sidebar-drawer");

  function abrirDrawer() {
    if (sidebarDrawer) sidebarDrawer.classList.add("open");
    if (drawerOverlay) drawerOverlay.classList.add("active");
  }

  function fecharDrawer() {
    if (sidebarDrawer) sidebarDrawer.classList.remove("open");
    if (drawerOverlay) drawerOverlay.classList.remove("active");
  }

  if (btnMenu) btnMenu.addEventListener("click", abrirDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener("click", fecharDrawer);

  const btnContaMobile = document.getElementById("btnContaMobile");
  const fotoContaMobile = document.getElementById("fotoContaMobile");

  if (estaLogado && fotoContaMobile) {
    fotoContaMobile.style.display = "block";
  }

  if (btnContaMobile) {
    btnContaMobile.addEventListener("click", () => {
      if (estaLogado) {
        abrirPopupConta();
      } else {
        window.location.href = "/cadastro";
      }
    });
  }
});
