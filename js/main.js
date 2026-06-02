document.addEventListener("DOMContentLoaded", () => {
  document.body.style.visibility = "visible";

  const btnConta  = document.getElementById("btnConta");
  const fotoConta = document.getElementById("fotoConta");
  const overlay   = document.getElementById("popupOverlay");
  const popup     = document.getElementById("popupConta");
  const btnVoltar = document.getElementById("btnVoltar");
  const btnSair   = document.getElementById("btnSair");

  const estaLogado = !!localStorage.getItem("token");

  if (estaLogado) {
    fotoConta.style.display = "block";
    btnConta.addEventListener("click", () => {
      overlay.classList.add("active");
      popup.classList.add("active");
    });
  } else {
    btnConta.addEventListener("click", () => {
      window.location.href = "/cadastro";
    });
  }

  function fecharPopup() {
    overlay.classList.remove("active");
    popup.classList.remove("active");
  }

  overlay.addEventListener("click", fecharPopup);
  btnVoltar.addEventListener("click", fecharPopup);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharPopup(); });

  btnSair.addEventListener("click", () => {
    localStorage.removeItem("token");
    window.location.href = "/login";
  });

  // ── Drawer mobile ──
const btnMenu      = document.getElementById("btnMenuMobile");
const drawerOverlay = document.getElementById("drawerOverlay");
const sidebarDrawer = document.querySelector(".sidebar-drawer");

function abrirDrawer() {
  sidebarDrawer.classList.add("open");
  drawerOverlay.classList.add("active");
}
function fecharDrawer() {
  sidebarDrawer.classList.remove("open");
  drawerOverlay.classList.remove("active");
}

if (btnMenu) btnMenu.addEventListener("click", abrirDrawer);
drawerOverlay.addEventListener("click", fecharDrawer);

// ── Botão conta mobile ──
const btnContaMobile  = document.getElementById("btnContaMobile");
const fotoContaMobile = document.getElementById("fotoContaMobile");

if (estaLogado && fotoContaMobile) {
  fotoContaMobile.style.display = "block";
}

if (btnContaMobile) {
  btnContaMobile.addEventListener("click", () => {
    if (estaLogado) {
      overlay.classList.add("active");
      popup.classList.add("active");
    } else {
      window.location.href = "/cadastro";
    }
  });
}
});
