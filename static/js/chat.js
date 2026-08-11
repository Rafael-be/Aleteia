/* =====================================================
   chat.js — Lógica exclusiva do chat
   Responsável por: envio de prompt, obtenção da resposta
                    da Aleteia, renderização estruturada
                    (veredicto colorido + ações) e layout
                    de conversa (header fixo / input fixo).
   Usado por: chat/chatIndex.html
   ===================================================== */

document.addEventListener("DOMContentLoaded", () => {

  const token           = localStorage.getItem("token");
  const textarea         = document.getElementById("promptInput");
  const btnEnviar         = document.getElementById("btnEnviar");
  const areaConversa     = document.getElementById("conversationArea");
  const btnNovaConversa  = document.getElementById("btnNovaConversa");
  const mainContent      = document.getElementById("mainContent");
  const chatSubtitle     = document.getElementById("chatSubtitle");

  if (!textarea || !btnEnviar) return;

  /* ── ID da conversa: persiste enquanto a aba estiver aberta. ── */
  let conversaId = sessionStorage.getItem("conversaId");
  if (!conversaId) {
    conversaId = crypto.randomUUID();
    sessionStorage.setItem("conversaId", conversaId);
  }

  let conversaJaNaSidebar = false;
  let ultimoPromptEnviado = "";

  /* =====================================================
     Mapeamento Veredicto (backend) → Veracidade (Figma)
     O gemini_service.py responde com:
       **Veredicto:** VERDADEIRO | FALSO | PARCIALMENTE VERDADEIRO | INCONCLUSIVO
     O layout usa o rótulo "Veracidade:" com outro vocabulário.
     Ajuste este mapa se o prompt do backend mudar.
     ===================================================== */
  const MAPA_VEREDICTO = {
    "VERDADEIRO":              { label: "Confirmada",  classe: "veracidade-verde"     },
    "FALSO":                   { label: "Desmentida",  classe: "veracidade-vermelha"  },
    "PARCIALMENTE VERDADEIRO": { label: "Parcial",     classe: "veracidade-amarela"   },
    "INCONCLUSIVO":            { label: "Inconclusivo", classe: "veracidade-neutra"   },
  };

  /* ── Liga/desliga o layout "conversa ativa" (header compacto + input fixo embaixo) ── */
  function ativarLayoutDeConversa() {
    if (mainContent && !mainContent.classList.contains("chat-ativo")) {
      mainContent.classList.add("chat-ativo");
    }
    if (chatSubtitle) chatSubtitle.style.display = "none";
  }

  function resetarLayoutInicial() {
    if (mainContent) mainContent.classList.remove("chat-ativo");
    if (chatSubtitle) chatSubtitle.style.display = "";
  }

  /* ── Extrai veredicto/análise/fontes do texto bruto vindo da IA ── */
  function parseRespostaIA(textoCru) {
    const texto = String(textoCru ?? "");

    const matchVeredicto = texto.match(/\*\*Veredicto:\*\*\s*([^\n]+)/i);
    const matchAnalise   = texto.match(/\*\*Análise:\*\*\s*([\s\S]*?)(?:\*\*Fontes consultadas:\*\*|$)/i);
    const matchFontes    = texto.match(/\*\*Fontes consultadas:\*\*\s*([\s\S]*)/i);

    const veredictoBruto = matchVeredicto ? matchVeredicto[1].trim().toUpperCase() : null;
    const info = MAPA_VEREDICTO[veredictoBruto] || null;

    return {
      label: info ? info.label : null,
      classe: info ? info.classe : "veracidade-neutra",
      analise: matchAnalise ? matchAnalise[1].trim() : texto.trim(),
      fontes: matchFontes ? matchFontes[1].trim() : null,
    };
  }

  /* ── Quebra texto em parágrafos/linhas preservando \n ── */
  function preencherTexto(container, texto) {
    String(texto ?? "").split("\n").forEach((linha, index) => {
      if (index > 0) container.appendChild(document.createElement("br"));
      if (linha.trim() !== "") container.appendChild(document.createTextNode(linha));
    });
  }

  /* ── Bolha simples (usuário ou mensagem de sistema/erro) ── */
  function adicionarBolha(texto, tipo) {
    if (!areaConversa) return null;

    const bolha = document.createElement("div");
    bolha.className = `bolha bolha-${tipo}`;
    preencherTexto(bolha, texto);

    areaConversa.appendChild(bolha);
    areaConversa.scrollTop = areaConversa.scrollHeight;
    return bolha;
  }

  /* ── Ícones SVG usados nas ações da resposta da IA ── */
  const ICONE_COPIAR = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2"/>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
    </svg>`;
  const ICONE_REGENERAR = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <polyline points="1 20 1 14 7 14"/>
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
    </svg>`;
  const ICONE_FALAR = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/>
    </svg>`;

  /* ── Resposta estruturada da IA: veredicto colorido + análise + fontes + ações ── */
  function adicionarRespostaIA(textoCru, promptOrigem) {
    if (!areaConversa) return null;

    const dados = parseRespostaIA(textoCru);
    const bloco = document.createElement("div");
    bloco.className = "resposta-ia";

    if (dados.label) {
      const linhaVeracidade = document.createElement("p");
      linhaVeracidade.className = "veracidade-label";
      linhaVeracidade.append("Veracidade: ");
      const valor = document.createElement("span");
      valor.className = `veracidade-valor ${dados.classe}`;
      valor.textContent = dados.label;
      linhaVeracidade.appendChild(valor);
      bloco.appendChild(linhaVeracidade);
    }

    const corpo = document.createElement("div");
    corpo.className = "resposta-corpo";
    preencherTexto(corpo, dados.analise);
    bloco.appendChild(corpo);

    if (dados.fontes) {
      const fontesEl = document.createElement("p");
      fontesEl.className = "resposta-fontes";
      const forte = document.createElement("strong");
      forte.textContent = "Fontes consultadas: ";
      fontesEl.appendChild(forte);
      fontesEl.appendChild(document.createTextNode(dados.fontes));
      bloco.appendChild(fontesEl);
    }

    const acoes = document.createElement("div");
    acoes.className = "resposta-acoes";
    acoes.innerHTML = `
      <button class="btn-icon-acao" data-acao="copiar" title="Copiar resposta">${ICONE_COPIAR}</button>
      <button class="btn-icon-acao" data-acao="regenerar" title="Gerar novamente">${ICONE_REGENERAR}</button>
      <button class="btn-icon-acao" data-acao="falar" title="Ouvir resposta">${ICONE_FALAR}</button>
    `;
    bloco.appendChild(acoes);

    // Ações: copiar / regenerar / falar
    acoes.querySelector('[data-acao="copiar"]').addEventListener("click", () => {
      navigator.clipboard?.writeText(textoCru || "");
    });

    acoes.querySelector('[data-acao="falar"]').addEventListener("click", () => {
      if (!("speechSynthesis" in window)) return;
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(dados.analise);
      utter.lang = "pt-BR";
      window.speechSynthesis.speak(utter);
    });

    acoes.querySelector('[data-acao="regenerar"]').addEventListener("click", () => {
      if (!promptOrigem) return;
      reenviarPrompt(promptOrigem);
    });

    areaConversa.appendChild(bloco);
    areaConversa.scrollTop = areaConversa.scrollHeight;
    return bloco;
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

  /* ── Envia um prompt específico à API e renderiza a resposta ── */
  async function chamarApiEExibir(prompt) {
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
        adicionarBolha("Você atingiu o limite diário de uso da Aleteia. Tente novamente amanhã.", "sistema");
        return;
      }

      if (!res.ok) {
        adicionarBolha(data.error || "Não foi possível obter resposta. Tente novamente.", "sistema");
        return;
      }

      adicionarRespostaIA(data.resposta, prompt);

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

  /* ── Reenvia um prompt já existente (usado pelo botão "Gerar novamente") ── */
  function reenviarPrompt(prompt) {
    chamarApiEExibir(prompt);
  }

  /* ── Enviar prompt digitado pelo usuário ── */
  async function enviarMensagem() {
    const prompt = textarea.value.trim();
    if (!prompt) return;

    ativarLayoutDeConversa();
    adicionarBolha(prompt, "usuario");
    ultimoPromptEnviado = prompt;

    textarea.value = "";
    textarea.style.height = "auto";

    await chamarApiEExibir(prompt);
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
      ativarLayoutDeConversa();

      data.mensagens.forEach((m) => {
        adicionarBolha(m.prompt, "usuario");
        adicionarRespostaIA(m.resposta, m.prompt);
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
      resetarLayoutInicial();
      textarea.value = "";
      textarea.style.height = "auto";
      textarea.focus();
    });
  }

});