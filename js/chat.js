/* =====================================================
   chat.js — Lógica exclusiva do chat
   Responsável por: envio de prompt, salvar no banco,
                    carregar histórico no aside
   Usado por: chat/chatIndex.html
   ===================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const token     = localStorage.getItem("token");
  const textarea  = document.getElementById("promptInput");
  const btnEnviar = document.getElementById("btnEnviar");

  if (!textarea || !btnEnviar) return;

  /* ── Auto-resize textarea ── */
  textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";

    const hasText = textarea.value.trim().length > 0;
    btnEnviar.disabled = !hasText;
    btnEnviar.classList.toggle("active", hasText);
  });

  /* ── Enter envia (Shift+Enter = nova linha) ── */
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!btnEnviar.disabled) enviarMensagem();
    }
  });

  btnEnviar.addEventListener("click", () => {
    if (!btnEnviar.disabled) enviarMensagem();
  });

  /* ── Enviar prompt ── */
  async function enviarMensagem() {
    const prompt = textarea.value.trim();
    if (!prompt) return;

    // 1. Salva no banco antes de qualquer outra coisa
    try {
      const res = await fetch("/api/chat/prompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ prompt })
      });

      if (!res.ok) {
        console.error("Erro ao salvar prompt no banco.");
        // Continua mesmo assim para não travar o usuário
      } else {
        const data = await res.json();
        // 2. Somente após salvar, adiciona no aside
        adicionarItemNoAside(data.chat);
      }
    } catch (err) {
      console.error("Falha na requisição de salvar prompt:", err);
    }

    // 3. Fluxo original: sessionStorage + redirect
    sessionStorage.setItem("promptInicial", prompt);
    const params = new URLSearchParams({ q: prompt });
    window.location.href = "/conversa?" + params.toString();
  }

  /* ── Adiciona item na lista do aside ── */
  function adicionarItemNoAside(chat) {
    const lista = document.getElementById("listaConversas");
    if (!lista) return;

    const item = document.createElement("li");
    item.textContent  = chat.prompt.substring(0, 40) + (chat.prompt.length > 40 ? "…" : "");
    item.dataset.id   = chat._id;
    item.style.cursor = "pointer";
    lista.prepend(item);
  }

  /* ── Carrega histórico do banco ao abrir a página ── */
  async function carregarHistorico() {
    if (!token) return;

    try {
      const res = await fetch("/api/chat/prompts", {
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

});
