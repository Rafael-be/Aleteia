import { chamarApi } from "./firebase-init.js";
import { consumirEventos } from "./chat-stream.js";

/* =====================================================
   chat.js — Lógica exclusiva do chat
   Responsável por: envio de prompt, obtenção da resposta
                    da Aleteia, renderização estruturada
                    (veredicto colorido + ações) e layout
                    de conversa (header fixo / input fixo).
   Usado por: chat/chatIndex.html
   ===================================================== */

document.addEventListener("DOMContentLoaded", () => {

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

  const urlParams = new URLSearchParams(window.location.search);
  const conversaIdQuery = urlParams.get("conversa_id");
  if (conversaIdQuery) {
    conversaId = conversaIdQuery;
    sessionStorage.setItem("conversaId", conversaId);
  }

  let conversaJaNaSidebar = false;
  let ultimoPromptEnviado = "";
  let requisicaoAtiva = null;

  function cancelarGeracao() {
    requisicaoAtiva?.abort();
    requisicaoAtiva = null;
    textarea.disabled = false;
    btnEnviar.disabled = !textarea.value.trim();
  }

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
    "STRONGLY_SUPPORTED": { label: "Fortemente sustentada", classe: "veracidade-verde" },
    "PREDOMINANTLY_SUPPORTED": { label: "Predominantemente sustentada", classe: "veracidade-verde" },
    "STRONGLY_CONTRADICTED": { label: "Fortemente contraditada", classe: "veracidade-vermelha" },
    "PREDOMINANTLY_CONTRADICTED": { label: "Predominantemente contraditada", classe: "veracidade-vermelha" },
    "CONTESTED": { label: "Evidências em conflito", classe: "veracidade-amarela" },
    "INCONCLUSIVE": { label: "Inconclusiva", classe: "veracidade-neutra" },
    "NOT_VERIFIABLE": { label: "Não verificável", classe: "veracidade-neutra" },
    "HUMAN_REVIEW_REQUIRED": { label: "Requer revisão humana", classe: "veracidade-amarela" },
  };

  const MOTIVOS = {
    INSUFFICIENT_EVIDENCE: "evidências insuficientes",
    MATERIAL_COVERAGE_INCOMPLETE: "faltam elementos materiais",
    ATTRIBUTES_MISSING: "atributos não observados",
    CONTEXT_INCOMPLETE: "contexto incompleto",
    DECOMPOSITION_INCOMPLETE: "alegações incompletas",
    PROVENANCE_UNCERTAIN: "origem das evidências incerta",
    RETRIEVAL_INCOMPLETE: "busca incompleta",
    REQUIREMENTS_NOT_MET: "requisitos não atendidos",
    DIMENSIONS_MISSING: "dimensões não medidas",
    MULTIPLE_CLAIMS: "consulte cada alegação",
    NOT_VERIFIABLE: "alegação não verificável",
    LOW_ACS: "qualidade do processo abaixo do limiar de decisão",
    HUMAN_REVIEW_REQUIRED: "revisão humana necessária",
  };

  function adicionarMetricas(container, metricas) {
    for (const m of (Array.isArray(metricas) ? metricas : []).slice(0, 2)) {
      if (!["ESS", "ACS"].includes(m.id)) continue;
      const linha = document.createElement("div");
      linha.className = "veredito-metrica";
      const valido = m.valid === true && typeof m.value === "number" && Number.isFinite(m.value) && m.value >= 0 && m.value <= 100;
      const rotulo = document.createElement("p");
      rotulo.className = "metrica-rotulo";
      rotulo.textContent = `${m.id} · ${m.id === "ESS" ? "Sustentação das evidências" : "Qualidade da análise"}`;
      const valor = document.createElement("strong");
      valor.textContent = valido ? `${m.value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}/100` : "Indisponível";
      rotulo.appendChild(valor);
      linha.appendChild(rotulo);
      if (valido) {
        const barra = document.createElement("meter");
        barra.className = `metrica-barra metrica-${m.id.toLowerCase()}`;
        barra.min = 0; barra.max = 100; barra.value = m.value;
        barra.setAttribute("aria-label", `${m.id}: ${m.value} de 100`);
        barra.textContent = `${m.value}/100`;
        const trilho = document.createElement("div");
        trilho.className = "metrica-trilho";
        trilho.appendChild(barra);
        if (m.id === "ESS") {
          const centro = document.createElement("span");
          centro.className = "metrica-centro";
          centro.setAttribute("aria-hidden", "true");
          trilho.appendChild(centro);
        }
        linha.appendChild(trilho);
        if (m.id === "ESS") {
          const eixo = document.createElement("p");
          eixo.className = "metrica-eixo";
          for (const texto of ["Contradiz", "50 · equilíbrio", "Sustenta"]) {
            const item = document.createElement("span"); item.textContent = texto; eixo.appendChild(item);
          }
          linha.appendChild(eixo);
        }
      } else {
        const motivo = document.createElement("small");
        motivo.textContent = MOTIVOS[m.reason] || "medição não disponível";
        linha.appendChild(motivo);
      }
      container.appendChild(linha);
    }
  }

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
    const matchVeredicto = String(textoCru ?? "").match(
      /^[ \t]*(?:#{1,6}[ \t]+)?(?:\*{1,2}|__)?veredi(?:c)?to(?:\*{1,2}|__)?[ \t]*:[ \t]*(?:\*{1,2}|__)?\s*(PARCIALMENTE VERDADEIRO|VERDADEIRO|FALSO|INCONCLUSIVO)\b/im
    );
    const texto = String(textoCru ?? "").replace(
      /^[ \t]*(?:#{1,6}[ \t]+)?(?:\*{1,2}|__)?veredi(?:c)?to(?:\*{1,2}|__)?[ \t]*:[^\n]*(?:\n[ \t]*(?:\*{1,2}|__)?(?:PARCIALMENTE VERDADEIRO|VERDADEIRO|FALSO|INCONCLUSIVO)[^\n]*)?/gim, ""
    );

    const matchAnalise   = texto.match(/\*\*Análise:\*\*\s*([\s\S]*?)(?:\*\*Fontes consultadas:\*\*|$)/i);
    const matchFontes    = texto.match(/\*\*Fontes consultadas:\*\*\s*([\s\S]*)/i);

    const veredictoBruto = matchVeredicto ? matchVeredicto[1].trim().toUpperCase() : null;
    const info = MAPA_VEREDICTO[veredictoBruto] || MAPA_VEREDICTO.INCONCLUSIVO;

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
  function adicionarRespostaIA(textoCru, promptOrigem, respostaFormatada = null, veredito = null) {
    if (!areaConversa) return null;

    const dados = parseRespostaIA(textoCru);
    const info = MAPA_VEREDICTO[veredito?.code];
    if (info) Object.assign(dados, info);
    const bloco = document.createElement("div");
    bloco.className = "resposta-ia";

    const corpo = document.createElement("div");
    corpo.className = "resposta-corpo";
    if (typeof respostaFormatada?.corpo_html === "string") {
      corpo.innerHTML = respostaFormatada.corpo_html;
    } else if (respostaFormatada?.analise_html) {
      corpo.innerHTML = respostaFormatada.analise_html;
    } else {
      preencherTexto(corpo, dados.analise);
    }
    bloco.appendChild(corpo);

    if (dados.fontes && typeof respostaFormatada?.corpo_html !== "string") {
      const fontesEl = document.createElement("p");
      fontesEl.className = "resposta-fontes";
      const forte = document.createElement("strong");
      forte.textContent = "Fontes consultadas: ";
      fontesEl.appendChild(forte);
      if (respostaFormatada?.fontes_html) {
        const fontesFormatadas = document.createElement("span");
        fontesFormatadas.innerHTML = respostaFormatada.fontes_html;
        fontesEl.appendChild(fontesFormatadas);
      } else {
        fontesEl.appendChild(document.createTextNode(dados.fontes));
      }
      bloco.appendChild(fontesEl);
    }

    const linhaVeracidade = document.createElement("p");
    linhaVeracidade.className = "veracidade-label";
    linhaVeracidade.append(veredito?.version === 2 ? "Avaliação: " : "Veracidade: ");
    const valorVeredito = document.createElement("span");
    valorVeredito.className = `veracidade-valor ${dados.classe}`;
    valorVeredito.textContent = dados.label;
    linhaVeracidade.appendChild(valorVeredito);
    bloco.appendChild(linhaVeracidade);
    if (veredito?.version === 2) {
      const painel = document.createElement("section");
      painel.className = "painel-indicadores";
      painel.setAttribute("aria-label", "Indicadores da análise");
      adicionarMetricas(painel, veredito.metrics);
      const nota = document.createElement("p");
      nota.className = "metrica-nota";
      nota.textContent = "Índices experimentais: não são probabilidades de verdade ou acerto.";
      painel.appendChild(nota);
      if (veredito.claim_details?.length) {
        const detalhes = document.createElement("details");
        const resumo = document.createElement("summary");
        resumo.textContent = "Alegações e limites da análise";
        detalhes.appendChild(resumo);
        for (const claim of veredito.claim_details.slice(0, 4)) {
          const item = document.createElement("div"); item.className = "metrica-alegacao";
          const titulo = document.createElement("p"); titulo.textContent = claim.text;
          item.appendChild(titulo);
          const estado = document.createElement("p");
          estado.textContent = MAPA_VEREDICTO[claim.state]?.label || "Inconclusiva";
          item.appendChild(estado);
          if (veredito.claim_details.length > 1) adicionarMetricas(item, claim.metrics);
          if (claim.reasons?.length) {
            const motivos = document.createElement("p"); motivos.className = "metrica-nota";
            motivos.textContent = claim.reasons.map((r) => MOTIVOS[r] || "requisito pendente").join("; ");
            item.appendChild(motivos);
          }
          detalhes.appendChild(item);
        }
        painel.appendChild(detalhes);
      }
      bloco.appendChild(painel);
    } else {
      const nota = document.createElement("small");
      nota.className = "metrica-nota";
      nota.textContent = "ESS e ACS não foram calculados nesta versão da resposta.";
      bloco.appendChild(nota);
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
      const indicadores = veredito?.version === 2 ? "\n\n" + (veredito.metrics || []).map((m) =>
        `${m.id}: ${m.valid && typeof m.value === "number" ? `${m.value}/100` : "indisponível"}`).join("\n") +
        "\nÍndices experimentais; não são probabilidades." : "";
      navigator.clipboard?.writeText((textoCru || "") + indicadores);
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
    if (requisicaoAtiva) return;
    const controle = new AbortController();
    requisicaoAtiva = controle;
    const idDaConversa = conversaId;
    textarea.disabled = true;
    btnEnviar.disabled = true;
    btnEnviar.classList.remove("active");
    // mostra feedback temporário enquanto a IA responde
    const loadingBubble = adicionarBolha("Preparando a consulta...", "sistema");
    loadingBubble.setAttribute("role", "status");
    loadingBubble.setAttribute("aria-live", "polite");
    const parcial = document.createElement("div");
    parcial.className = "resposta-ia resposta-stream";
    const corpoParcial = document.createElement("div");
    corpoParcial.className = "resposta-corpo";
    parcial.appendChild(corpoParcial);
    areaConversa.appendChild(parcial);
    let texto = "";
    let concluida = false;
    let veredito = null;
    let htmlParcial = null;

    try {
      const res = await chamarApi("/api/chat/mensagem", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({ conversa_id: idDaConversa, prompt }),
        signal: controle.signal
      });

      if (!res) throw new Error("Faça login para continuar.");
      if (!res.ok) {
        const data = await res.json();
        throw new Error(res.status === 429
          ? (data.code === "rate_limited" ? "Aguarde antes de enviar outra pergunta." : "Você atingiu o limite diário de uso da Aleteia. Tente novamente amanhã.")
          : data.error || "Não foi possível obter resposta.");
      }
      await consumirEventos(res, (evento) => {
        if (controle.signal.aborted) return;
        if (evento.type === "stage") loadingBubble.textContent = evento.message;
        if (evento.type === "delta") {
          texto += evento.text;
          if (typeof evento.html === "string") {
            htmlParcial = evento.html;
            corpoParcial.innerHTML = evento.html;
          }
          else corpoParcial.textContent = texto;
          areaConversa.scrollTop = areaConversa.scrollHeight;
        }
        if (evento.type === "verdict") veredito = evento.veredito;
        if (evento.type === "error") {
          veredito = null;
          throw new Error(evento.message);
        }
        if (evento.type === "done") {
          concluida = true;
          parcial.remove();
          adicionarRespostaIA(evento.resposta, prompt, evento.resposta_formatada, evento.veredito);
        }
      });
      if (!concluida) throw new Error("A conexão foi interrompida antes de concluir a resposta.");

      if (!conversaJaNaSidebar && window.adicionarItemNoAside) {
        window.adicionarItemNoAside({ _id: conversaId, prompt });
        conversaJaNaSidebar = true;
      }
    } catch (err) {
      if (controle.signal.aborted) return;
      console.error("Erro ao obter resposta da IA:", err);
      // remove loading e exibe erro
      if (typeof loadingBubble !== 'undefined' && loadingBubble && loadingBubble.parentNode) loadingBubble.remove();
      if (!concluida) {
        parcial.remove();
        if (texto.trim()) {
          const incompleta = document.createElement("div");
          incompleta.className = "resposta-ia resposta-incompleta";
          const aviso = document.createElement("p");
          aviso.textContent = "Resposta interrompida — análise não concluída.";
          const corpo = document.createElement("div");
          corpo.className = "resposta-corpo";
          if (typeof htmlParcial === "string") corpo.innerHTML = htmlParcial;
          else preencherTexto(corpo, texto);
          incompleta.appendChild(aviso);
          incompleta.appendChild(corpo);
          areaConversa.appendChild(incompleta);
        }
      }
      adicionarBolha(err.message || "Não foi possível obter resposta. Tente novamente.", "sistema");
    } finally {
      loadingBubble.remove();
      if (requisicaoAtiva === controle) {
        requisicaoAtiva = null;
        textarea.disabled = false;
        btnEnviar.disabled = !textarea.value.trim();
        btnEnviar.classList.toggle("active", !btnEnviar.disabled);
        textarea.focus();
      }
      window.dispatchEvent?.(new Event("aleteia:chat-idle"));
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
    cancelarGeracao();

    try {
      const res = await chamarApi(`/api/chat/conversas/${idConversa}`);
      if (!res.ok) return;

      const data = await res.json();

      areaConversa.innerHTML = "";
      ativarLayoutDeConversa();

      data.mensagens.forEach((m) => {
        adicionarBolha(m.prompt, "usuario");
        adicionarRespostaIA(m.resposta, m.prompt, m.resposta_formatada, m.veredito);
      });

      conversaId = idConversa;
      sessionStorage.setItem("conversaId", conversaId);
      conversaJaNaSidebar = true;
    } catch (err) {
      console.error("Erro ao carregar conversa:", err);
    }
  };

  function carregarConversaDaUrl() {
    if (!conversaIdQuery) return;
    if (!window.carregarConversa) return;
    window.carregarConversa(conversaIdQuery);
  }

  window.iniciarNovaConversa = function () {
    cancelarGeracao();
    conversaId = crypto.randomUUID();
    sessionStorage.setItem("conversaId", conversaId);
    conversaJaNaSidebar = false;
    if (areaConversa) areaConversa.innerHTML = "";
    resetarLayoutInicial();
    textarea.value = "";
    textarea.style.height = "auto";
    textarea.focus();
  };

  window.addEventListener("conversaApagada", ({ detail: idConversa }) => {
    if (idConversa === conversaId) window.iniciarNovaConversa();
  });

  carregarConversaDaUrl();

  window.aleteiaEnviarSelecao = (text) => {
    if (requisicaoAtiva || textarea.value.trim()) return false;
    textarea.value = text;
    enviarMensagem();
    return true;
  };
  textarea.addEventListener("input", () => window.dispatchEvent(new Event("aleteia:chat-idle")));

  /* ── Nova conversa ── */
  if (btnNovaConversa) {
    btnNovaConversa.addEventListener("click", (e) => {
      e.preventDefault();
      window.iniciarNovaConversa();
    });
  }

});
