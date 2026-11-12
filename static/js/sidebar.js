(() => {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  const mobile = window.matchMedia("(max-width: 767px)");
  const layout = document.querySelector(".app-layout");
  const main = layout.querySelector("main");
  const header = document.querySelector(".mobile-header");
  const overlay = document.getElementById("drawerOverlay");
  const openButtons = [document.getElementById("btnMenuMobile"), document.getElementById("btnAbrirSidebar")];
  const closeButton = document.getElementById("btnFecharSidebar");
  const rail = document.querySelector(".sidebar-rail");
  let open = !mobile.matches;

  function setOpen(value, restoreFocus = false) {
    open = value;
    const modal = mobile.matches && open;
    layout.classList.toggle("sidebar-collapsed", !open);
    sidebar.classList.toggle("open", open);
    sidebar.inert = !open;
    sidebar.setAttribute("aria-hidden", String(!open));
    overlay.classList.toggle("active", modal);
    document.body.classList.toggle("drawer-open", modal);
    main.inert = modal;
    header.inert = modal;
    rail.inert = open;
    openButtons.forEach(button => button?.setAttribute("aria-expanded", String(open)));
    if (modal) closeButton.focus();
    else if (restoreFocus) openButtons[mobile.matches ? 0 : 1]?.focus();
  }

  openButtons.forEach(button => button?.addEventListener("click", () => setOpen(true)));
  document.querySelectorAll("[data-sidebar-action]").forEach(button => {
    button.addEventListener("click", () => {
      setOpen(true);
      const action = button.dataset.sidebarAction;
      if (action === "search") {
        document.getElementById("inputPesquisarConversas").focus({ preventScroll: true });
      } else if (action === "new") {
        document.getElementById("btnNovaConversa").click();
      } else if (window.location.pathname !== "/") {
        window.location.href = "/";
      } else {
        closeButton.focus();
      }
    });
  });
  closeButton.addEventListener("click", () => setOpen(false, true));
  overlay.addEventListener("click", () => setOpen(false, true));
  document.addEventListener("keydown", event => {
    if (!open) return;
    if (event.key === "Escape") setOpen(false, true);
    if (event.key !== "Tab" || !mobile.matches) return;
    const controls = [...sidebar.querySelectorAll('a[href], button:not(:disabled), input:not(:disabled), [tabindex="0"]')]
      .filter(element => element.getClientRects().length);
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  sidebar.addEventListener("click", event => {
    if (mobile.matches && event.target.closest('a[href], #listaConversas li') && !event.target.closest(".btn-excluir-conversa")) setOpen(false, true);
  });
  mobile.addEventListener("change", () => setOpen(!mobile.matches, true));
  setOpen(open);
})();
