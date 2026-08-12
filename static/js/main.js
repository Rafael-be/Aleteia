/* =====================================================
   main.js — Lógica compartilhada entre páginas
   Responsável por: popup de conta, drawer mobile,
                    anti-FOUC, histórico do aside
   Usado por: main-desktop.html, chatIndex.html
   ===================================================== */

document.addEventListener("DOMContentLoaded", () => {

  /* ── Anti-FOUC ── */
  document.body.style.visibility = "visible";
  document.body.style.opacity    = "1";

  const token      = localStorage.getItem("token");
  const estaLogado = !!token;

  /* ── Popup de conta (desktop) ── */
  const btnConta  = document.getElementById("btnConta");
  const fotoConta = document.getElementById("fotoConta");
  const overlay   = document.getElementById("popupOverlay");
  const popup     = document.getElementById("popupConta");
  const btnVoltar = document.getElementById("btnVoltar");
  const btnSair   = document.getElementById("btnSair");

  if (btnConta) {
    if (estaLogado) {
      if (fotoConta) fotoConta.style.display = "block";
      btnConta.addEventListener("click", () => {
        overlay.classList.add("active");
        popup.classList.add("active");
      });
    } else {
      btnConta.addEventListener("click", () => {
        window.location.href = "/cadastro";
      });
    }
  }

  function fecharPopup() {
    if (overlay) overlay.classList.remove("active");
    if (popup)   popup.classList.remove("active");
  }

  if (overlay)   overlay.addEventListener("click", fecharPopup);
  if (btnVoltar) btnVoltar.addEventListener("click", fecharPopup);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fecharPopup(); });

  if (btnSair) {
    btnSair.addEventListener("click", () => {
      localStorage.removeItem("token");
      window.location.href = "/login";
    });
  }

  /* ── Drawer mobile ── */
  const btnMenu       = document.getElementById("btnMenuMobile");
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

  window.fecharDrawer = fecharDrawer;

  if (btnMenu)       btnMenu.addEventListener("click", abrirDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener("click", fecharDrawer);

  /* ── Botão conta mobile ── */
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

  /* ── Botão 'Nova conversa' compartilha comportamento entre página inicial e chat ── */
  const btnNovaConversa = document.getElementById("btnNovaConversa");
  if (btnNovaConversa) {
    btnNovaConversa.addEventListener("click", (e) => {
      if (window.iniciarNovaConversa) {
        e.preventDefault();
        window.iniciarNovaConversa();
        return;
      }
      window.location.href = "/chat";
    });
  }

  /* ── Histórico do aside (compartilhado) ── */
  function adicionarItemNoAside(chat) {
    const lista = document.getElementById("listaConversas");
    if (!lista) return;

    const item = document.createElement("li");
    item.textContent  = chat.prompt.substring(0, 40) + (chat.prompt.length > 40 ? "…" : "");
    item.dataset.id   = chat._id;
    item.style.cursor = "pointer";

    // NOVO: clicar numa conversa antiga reabre ela no chat.js
    item.addEventListener("click", () => {
      if (window.carregarConversa) {
        window.carregarConversa(chat._id);
        if (window.fecharDrawer) window.fecharDrawer();
        return;
      }
      window.location.href = "/chat?conversa_id=" + encodeURIComponent(chat._id);
    });

    lista.prepend(item);
  }

  async function carregarHistorico() {
    if (!token) return;

    try {
      const res = await fetch("/api/chat/conversas", {  // NOVO: era /api/chat/prompts
        headers: { "Authorization": `Bearer ${token}` }
      });

      if (!res.ok) return;

      const data = await res.json();
      data.prompts.forEach((chat) => adicionarItemNoAside(chat));
    } catch (err) {
      console.error("Erro ao carregar histórico:", err);
    }
  }

  carregarHistorico();

  /* ── Exporta para uso no chat.js ── */
  window.adicionarItemNoAside = adicionarItemNoAside;

});