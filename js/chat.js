/* =====================================================
   chat.js — Lógica exclusiva do chat
   Responsável por: envio de prompt, obtenção da resposta
                    da Aleteia (via OpenAI) e exibição da
                    conversa como bolhas de mensagem
   Usado por: chat/chatIndex.html
   ===================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const token        = localStorage.getItem("token");
  const textarea     = document.getElementById("promptInput");
  const btnEnviar     = document.getElementById("btnEnviar");
  const areaConversa = document.getElementById("conversationArea");
  const btnNovaConversa = document.getElementById("btnNovaConversa");

  if (!textarea || !btnEnviar) return;

  /* ── ID da conversa: persiste enquanto a aba estiver aberta.
     Só é trocado quando o usuário clica em "Nova conversa" ou
     abre uma conversa antiga pela sidebar. ── */
  let conversaId = sessionStorage.getItem("conversaId");
  if (!conversaId) {
    conversaId = crypto.randomUUID();
    sessionStorage.setItem("conversaId", conversaId);
  }

  // Controla se já adicionamos essa conversa na sidebar nesta sessão
  let conversaJaNaSidebar = false;

  function adicionarBolha(texto, tipo) {
    // tipo: "usuario" | "ia" | "sistema"
    if (!areaConversa) return;

    const bolha = document.createElement("div");
    bolha.className = `bolha bolha-${tipo}`;

    String(texto ?? "").split("\n").forEach((linha, index) => {
      if (index > 0) bolha.appendChild(document.createElement("br"));
      bolha.appendChild(document.createTextNode(linha));
    });

    areaConversa.appendChild(bolha);
    areaConversa.scrollTop = areaConversa.scrollHeight;
  }

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

  /* ── Enviar prompt e obter resposta da Aleteia ── */
  async function enviarMensagem() {
    const prompt = textarea.value.trim();
    if (!prompt) return;

    adicionarBolha(prompt, "usuario");

    textarea.value = "";
    textarea.style.height = "auto";
    textarea.disabled = true;
    btnEnviar.disabled = true;
    btnEnviar.classList.remove("active");

    try {
      const res = await fetch("/api/chat/mensagem", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ conversa_id: conversaId, prompt })
      });

      const data = await res.json();

      if (res.status === 429) {
        adicionarBolha(
          "Você atingiu o limite diário de uso da Aleteia. Tente novamente amanhã.",
          "sistema"
        );
        return;
      }

      if (!res.ok) {
        adicionarBolha(data.error || "Não foi possível obter resposta. Tente novamente.", "sistema");
        return;
      }

      adicionarBolha(data.resposta, "ia");

      if (!conversaJaNaSidebar && window.adicionarItemNoAside) {
        window.adicionarItemNoAside({ _id: conversaId, prompt });
        conversaJaNaSidebar = true;
      }
    } catch (err) {
      console.error("Erro ao obter resposta da IA:", err);
      adicionarBolha("Não foi possível obter resposta. Tente novamente.", "sistema");
    } finally {
      textarea.disabled = false;
      textarea.focus();
    }
  }

  /* ── Reabrir uma conversa antiga (chamado pelo main.js ao clicar na sidebar) ── */
  window.carregarConversa = async function (idConversa) {
    if (!areaConversa) return;

    try {
      const res = await fetch(`/api/chat/conversas/${idConversa}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) return;

      const data = await res.json();

      areaConversa.innerHTML = "";
      data.mensagens.forEach((m) => {
        adicionarBolha(m.prompt, "usuario");
        adicionarBolha(m.resposta, "ia");
      });

      conversaId = idConversa;
      sessionStorage.setItem("conversaId", conversaId);
      conversaJaNaSidebar = true;
    } catch (err) {
      console.error("Erro ao carregar conversa:", err);
    }
  };

  /* ── Nova conversa ── */
  if (btnNovaConversa) {
    btnNovaConversa.addEventListener("click", (e) => {
      e.preventDefault();
      conversaId = crypto.randomUUID();
      sessionStorage.setItem("conversaId", conversaId);
      conversaJaNaSidebar = false;
      if (areaConversa) areaConversa.innerHTML = "";
      textarea.value = "";
      textarea.style.height = "auto";
      textarea.focus();
    });
  }

});