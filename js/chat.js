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
// Gera ID de sessão único por aba do navegador
const sessaoId = crypto.randomUUID();

async function enviarMensagem() {
    const prompt = textarea.value.trim();
    if (!prompt) return;

    // Desabilita input enquanto processa
    textarea.disabled = true;
    btnEnviar.disabled = true;
    btnEnviar.classList.remove("active");

    // 1. Salva no banco (igual ao que você já fazia)
    try {
        const res = await fetch("/api/chat/prompt", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ prompt })
        });

        if (res.ok) {
            const data = await res.json();
            window.adicionarItemNoAside(data.chat);
        }
    } catch (err) {
        console.error("Erro ao salvar prompt:", err);
    }

    // 2. Chama a Aleteia (NOVO)
    try {
        const res = await fetch("/api/chat/responder", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ mensagem: prompt, sessaoId })
        });

        const data = await res.json();

        // 3. Leva a resposta para a página /conversa via sessionStorage
        sessionStorage.setItem("promptInicial", prompt);
        sessionStorage.setItem("respostaIA", data.resposta || data.erro || "Sem resposta.");
        window.location.href = "/conversa?" + new URLSearchParams({ q: prompt });

    } catch (err) {
        console.error("Erro ao obter resposta da IA:", err);
        sessionStorage.setItem("promptInicial", prompt);
        sessionStorage.setItem("respostaIA", "Não foi possível obter resposta. Tente novamente.");
        window.location.href = "/conversa?" + new URLSearchParams({ q: prompt });
    }
}


});
