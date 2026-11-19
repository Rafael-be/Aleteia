import { authPronta, chamarApi, chaveRascunhoLogin } from "./firebase-init.js";
import { consumirEventos } from "./chat-stream.js";
import { mostrarFeedback } from "./feedback.js";

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
  const seletorModelo = document.getElementById('seletorModelo');
  const botaoModelo = document.getElementById('botaoModelo');
  const nomeModelo = document.getElementById('nomeModelo');
  const menuModelos = document.getElementById('menuModelos');
  const opcoesModelo = [document.getElementById('modeloBasico'), document.getElementById('modeloExperimental')];
  const avisoModoExperimental = document.getElementById("avisoModoExperimental");

  if (!textarea || !btnEnviar) return;
  let modeloSelecionado = 'standard';
  const avisoExperimental = {
    temporizador: null,
    esconder: null,
    inicio: 0,
    restante: 15000,
    versao: 0,
    pausado: false,
  };
  const barraAvisoExperimental = avisoModoExperimental?.querySelector(".aviso-modo-experimental-progresso");

  function cancelarTemporizadorAvisoExperimental() {
    if (avisoExperimental.temporizador) clearTimeout(avisoExperimental.temporizador);
    avisoExperimental.temporizador = null;
  }

  function encerrarAvisoExperimental() {
    const versao = ++avisoExperimental.versao;
    cancelarTemporizadorAvisoExperimental();
    if (!avisoModoExperimental) return;
    avisoModoExperimental.classList.remove("visivel");
    clearTimeout(avisoExperimental.esconder);
    avisoExperimental.esconder = setTimeout(() => {
      if (avisoExperimental.versao === versao && !avisoModoExperimental.classList.contains("visivel")) {
        avisoModoExperimental.hidden = true;
      }
    }, 160);
    avisoExperimental.esconder?.unref?.();
  }

  function iniciarContagemAvisoExperimental() {
    if (!avisoModoExperimental || avisoExperimental.pausado) return;
    cancelarTemporizadorAvisoExperimental();
    avisoExperimental.inicio = Date.now();
    if (barraAvisoExperimental) {
      barraAvisoExperimental.style.animation = "none";
      void barraAvisoExperimental.offsetWidth;
      barraAvisoExperimental.style.animation = `aviso-experimental-progresso 15000ms linear -${15000 - avisoExperimental.restante}ms forwards`;
      barraAvisoExperimental.style.animationPlayState = "running";
    }
    const versao = avisoExperimental.versao;
    avisoExperimental.temporizador = setTimeout(() => {
      if (avisoExperimental.versao === versao) encerrarAvisoExperimental();
    }, avisoExperimental.restante);
    avisoExperimental.temporizador?.unref?.();
  }

  function pausarAvisoExperimental() {
    if (!avisoModoExperimental || avisoModoExperimental.hidden || avisoExperimental.pausado) return;
    avisoExperimental.pausado = true;
    avisoExperimental.restante = Math.max(0, avisoExperimental.restante - (Date.now() - avisoExperimental.inicio));
    cancelarTemporizadorAvisoExperimental();
    if (barraAvisoExperimental) barraAvisoExperimental.style.animationPlayState = "paused";
  }

  function retomarAvisoExperimental() {
    if (!avisoExperimental.pausado || avisoModoExperimental?.hidden) return;
    avisoExperimental.pausado = false;
    iniciarContagemAvisoExperimental();
  }

  function mostrarAvisoExperimental() {
    if (!avisoModoExperimental) return;
    avisoExperimental.versao += 1;
    clearTimeout(avisoExperimental.esconder);
    avisoExperimental.restante = 15000;
    avisoExperimental.pausado = false;
    avisoModoExperimental.hidden = false;
    avisoModoExperimental.classList.add("visivel");
    iniciarContagemAvisoExperimental();
  }

  function fecharModelos(devolverFoco = false) {
    limparReposicionamentoModelos();
    if (menuModelos) menuModelos.hidden = true;
    menuModelos?.classList.remove("menu-modelos--down");
    menuModelos?.style.removeProperty?.("max-height");
    botaoModelo?.setAttribute('aria-expanded', 'false');
    if (devolverFoco) botaoModelo?.focus();
  }

  let limparReposicionamentoModelos = () => {};

  function posicionarModelos() {
    if (!botaoModelo || !menuModelos || typeof botaoModelo.getBoundingClientRect !== "function") return;
    const viewport = window.visualViewport;
    const topoViewport = viewport?.offsetTop ?? 0;
    const baseViewport = topoViewport + (viewport?.height ?? window.innerHeight);
    const margem = 8;
    const gatilho = botaoModelo.getBoundingClientRect();
    const acima = Math.max(0, gatilho.top - topoViewport - margem);
    const abaixo = Math.max(0, baseViewport - gatilho.bottom - margem);
    const alturaMenu = menuModelos.scrollHeight || menuModelos.offsetHeight || 0;
    const abreAbaixo = alturaMenu > acima && abaixo > acima;
    const espacoDisponivel = abreAbaixo ? abaixo : acima;
    menuModelos.classList.toggle("menu-modelos--down", abreAbaixo);
    menuModelos.style.maxHeight = `${Math.floor(espacoDisponivel)}px`;
  }

  function selecionarModelo(mode, anunciarMudanca = true) {
    const modoAnterior = modeloSelecionado;
    modeloSelecionado = mode;
    const experimental = mode === 'experimental';
    if (nomeModelo) nomeModelo.textContent = experimental ? 'Complexo' : 'Rápido';
    botaoModelo?.setAttribute('aria-label', `Modelo selecionado: ${experimental ? 'Complexo' : 'Rápido'}. Escolher modelo.`);
    opcoesModelo.forEach((opcao, index) => opcao?.setAttribute('aria-checked', String(experimental === (index === 1))));
    if (experimental && modoAnterior !== 'experimental' && anunciarMudanca) mostrarAvisoExperimental();
    if (!experimental && modoAnterior === 'experimental') encerrarAvisoExperimental();
  }

  function abrirModelos() {
    if (!botaoModelo || botaoModelo.disabled || !menuModelos) return;
    menuModelos.hidden = false;
    posicionarModelos();
    const reposicionar = () => posicionarModelos();
    window.addEventListener("resize", reposicionar);
    window.visualViewport?.addEventListener("resize", reposicionar);
    window.visualViewport?.addEventListener("scroll", reposicionar);
    limparReposicionamentoModelos = () => {
      window.removeEventListener?.("resize", reposicionar);
      window.visualViewport?.removeEventListener("resize", reposicionar);
      window.visualViewport?.removeEventListener("scroll", reposicionar);
      limparReposicionamentoModelos = () => {};
    };
    botaoModelo.setAttribute('aria-expanded', 'true');
    opcoesModelo[modeloSelecionado === 'experimental' ? 1 : 0]?.focus();
  }

  function bloquearModelo(bloqueado) {
    if (botaoModelo) botaoModelo.disabled = bloqueado;
    opcoesModelo.forEach((opcao) => { if (opcao) opcao.disabled = bloqueado; });
    if (bloqueado) fecharModelos();
  }

  selecionarModelo('standard', false);
  if (avisoModoExperimental) avisoModoExperimental.hidden = true;
  avisoModoExperimental?.querySelector(".aviso-modo-experimental-fechar")?.addEventListener("click", encerrarAvisoExperimental);
  avisoModoExperimental?.addEventListener("mouseenter", pausarAvisoExperimental);
  avisoModoExperimental?.addEventListener("mouseleave", retomarAvisoExperimental);
  avisoModoExperimental?.addEventListener("focusin", pausarAvisoExperimental);
  avisoModoExperimental?.addEventListener("focusout", (event) => {
    if (!avisoModoExperimental.contains(event.relatedTarget)) retomarAvisoExperimental();
  });
  fecharModelos();
  botaoModelo?.addEventListener('click', () => menuModelos?.hidden ? abrirModelos() : fecharModelos());
  botaoModelo?.addEventListener('keydown', (event) => {
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); abrirModelos(); }
    if (event.key === 'Escape') fecharModelos();
  });
  opcoesModelo.forEach((opcao, index) => opcao?.addEventListener('click', () => {
    if (botaoModelo?.disabled) return;
    selecionarModelo(index === 1 ? 'experimental' : 'standard');
    fecharModelos(true);
  }));
  menuModelos?.addEventListener('keydown', (event) => {
    const index = event.target === opcoesModelo[1] ? 1 : 0;
    if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape', 'Tab'].includes(event.key)) {
      if (event.key === 'Tab') { fecharModelos(true); return; }
      event.preventDefault();
      if (event.key === 'Escape') { fecharModelos(true); return; }
      opcoesModelo[event.key === 'Home' ? 0 : event.key === 'End' ? 1 : 1-index]?.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (seletorModelo && !seletorModelo.contains(event.target)) fecharModelos();
  });

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
  let chatBloqueado = false;
  let editandoRascunhoLogin = false;
  const botaoAnexos = document.getElementById("botaoAnexos");
  const opcoesAnexos = document.getElementById("opcoesAnexos");
  const selecionarImagens = document.getElementById("selecionarImagens");
  const arquivosImagens = document.getElementById("arquivosImagens");
  const imagensPrompt = document.getElementById("imagensPrompt");
  const avisoImagens = document.getElementById("avisoImagens");
  const anexosPrompt = document.getElementById("anexosPrompt");
  const formatosImagens = new Set(["image/png", "image/jpeg", "image/webp"]);
  const limiteImagens = 3;
  const imagens = [];

  function mostrarAvisoImagens(mensagem = "") {
    avisoImagens.textContent = mensagem;
    avisoImagens.hidden = !mensagem;
  }

  function abrirOpcoesAnexos(aberto) {
    opcoesAnexos.hidden = !aberto;
    botaoAnexos.setAttribute("aria-expanded", String(aberto));
  }

  function miniaturaImagem(anexo, remover) {
    const miniatura = document.createElement("div");
    miniatura.className = "miniatura-prompt";
    if (anexo.url) {
      const imagem = document.createElement("img");
      imagem.src = anexo.url;
      imagem.alt = anexo.nome;
      miniatura.appendChild(imagem);
    } else {
      miniatura.setAttribute("aria-label", "Carregando imagem");
    }
    if (remover) {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.textContent = "×";
      botao.setAttribute("aria-label", `Remover ${anexo.nome}`);
      botao.addEventListener("click", remover);
      miniatura.appendChild(botao);
    }
    return miniatura;
  }

  function atualizarImagensPrompt() {
    imagensPrompt.replaceChildren(...imagens.map(anexo => miniaturaImagem(anexo, () => {
      imagens.splice(imagens.indexOf(anexo), 1);
      mostrarAvisoImagens();
      atualizarImagensPrompt();
      textarea.focus();
    })));
    imagensPrompt.hidden = imagens.length === 0;
    atualizarCompositor();
  }

  function limparImagensPrompt() {
    imagens.length = 0;
    mostrarAvisoImagens();
    abrirOpcoesAnexos(false);
    atualizarImagensPrompt();
  }

  function anexarImagens(arquivos) {
    if (requisicaoAtiva || chatBloqueado) return;
    mostrarAvisoImagens();
    for (const arquivo of arquivos) {
      if (imagens.length >= limiteImagens) {
        mostrarAvisoImagens("Você pode anexar até 3 imagens por mensagem.");
        break;
      }
      if (!formatosImagens.has(arquivo.type)) {
        mostrarAvisoImagens("Use imagens PNG, JPEG ou WebP.");
        continue;
      }
      if (arquivo.size > 4 * 1024 * 1024) {
        mostrarAvisoImagens("Envie imagens de até 4 MB cada.");
        continue;
      }
      const anexo = { nome: arquivo.name || "Imagem anexada", url: null };
      imagens.push(anexo);
      const leitor = new FileReader();
      leitor.addEventListener("load", () => {
        if (!imagens.includes(anexo)) return;
        anexo.url = leitor.result;
        atualizarImagensPrompt();
      });
      leitor.addEventListener("error", () => {
        const indice = imagens.indexOf(anexo);
        if (indice < 0) return;
        imagens.splice(indice, 1);
        mostrarAvisoImagens("Não foi possível abrir a imagem.");
        atualizarImagensPrompt();
      });
      leitor.readAsDataURL(arquivo);
    }
    atualizarImagensPrompt();
  }

  botaoAnexos.addEventListener("click", () => {
    const abrir = opcoesAnexos.hidden;
    abrirOpcoesAnexos(abrir);
    if (abrir) selecionarImagens.focus();
  });
  selecionarImagens.addEventListener("click", () => {
    abrirOpcoesAnexos(false);
    arquivosImagens.click();
    botaoAnexos.focus();
  });
  anexosPrompt.addEventListener("keydown", e => {
    if (e.key !== "Escape" || opcoesAnexos.hidden) return;
    abrirOpcoesAnexos(false);
    botaoAnexos.focus();
  });
  document.addEventListener("click", e => {
    if (!anexosPrompt.contains(e.target)) abrirOpcoesAnexos(false);
  });
  arquivosImagens.addEventListener("change", () => {
    anexarImagens(arquivosImagens.files);
    arquivosImagens.value = "";
    textarea.focus();
  });
  document.addEventListener("paste", e => {
    if (requisicaoAtiva || chatBloqueado || e.defaultPrevented) return;
    if (e.target !== textarea && e.target.closest?.("input, textarea, [contenteditable]")) return;
    const arquivos = Array.from(e.clipboardData?.files || []).filter(arquivo => arquivo.type.startsWith("image/"));
    if (!arquivos.length) return;
    e.preventDefault();
    anexarImagens(arquivos);
    textarea.focus();
  });

  function atualizarCompositor() {
    const gerando = Boolean(requisicaoAtiva);
    const rotulo = gerando ? "Cancelar resposta" : "Enviar";
    textarea.disabled = gerando || chatBloqueado;
    botaoAnexos.disabled = gerando || chatBloqueado;
    if (botaoAnexos.disabled) abrirOpcoesAnexos(false);
    btnEnviar.disabled = !gerando && (chatBloqueado || imagens.some(anexo => !anexo.url)
      || (!textarea.value.trim() && !imagens.length));
    btnEnviar.classList.toggle("active", !btnEnviar.disabled);
    btnEnviar.classList.toggle("cancelando", gerando);
    btnEnviar.title = rotulo;
    btnEnviar.setAttribute("aria-label", rotulo);
  }

  document.addEventListener("aleteia:chat-bloqueado", ({ detail }) => {
    chatBloqueado = detail;
    atualizarCompositor();
    if (!chatBloqueado && !requisicaoAtiva) window.dispatchEvent(new Event("aleteia:chat-idle"));
  });

  function cancelarGeracao() {
    if (!requisicaoAtiva) return;
    requisicaoAtiva.abort();
    requisicaoAtiva = null;
    bloquearModelo(false);
    atualizarCompositor();
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
    "NO_SUPPORT_FOUND": { label: "Sem sustentação nas fontes consultadas", classe: "veracidade-amarela" },
    "MIXED": { label: "Parcialmente sustentada · contextos distintos", classe: "veracidade-amarela" },
    "INCONCLUSIVE": { label: "Inconclusiva", classe: "veracidade-neutra" },
    "NOT_VERIFIABLE": { label: "Não verificável", classe: "veracidade-neutra" },
    "HUMAN_REVIEW_REQUIRED": { label: "Requer revisão humana", classe: "veracidade-amarela" },
  };

  const MOTIVOS = {
    SEARCH_WITHOUT_SUPPORT: "nenhuma confirmação localizada; isso não prova que o fato nunca ocorreu",
    DIRECTION_UNDETERMINED: "as fontes não permitem determinar se há apoio ou contradição",
    PROVISIONAL_DIRECTION: "direção provisória das evidências; atributos incompletos reduzem a qualidade da avaliação",
    INSUFFICIENT_EVIDENCE: "evidências insuficientes",
    MATERIAL_COVERAGE_INCOMPLETE: "faltam elementos materiais",
    ATTRIBUTES_MISSING: "atributos não observados",
    CONTEXT_INCOMPLETE: "contexto incompleto",
    DECOMPOSITION_INCOMPLETE: "alegações incompletas",
    PROVENANCE_UNCERTAIN: "origem das evidências incerta",
    RETRIEVAL_INCOMPLETE: "busca incompleta",
    REQUIREMENTS_NOT_MET: "requisitos não atendidos",
    DIMENSIONS_MISSING: "dimensões não medidas",
    MULTIPLE_CLAIMS: "os pontos avaliados não permitem uma medida conjunta",
    NOT_VERIFIABLE: "alegação não verificável",
    LOW_ACS: "qualidade limitada nos aspectos medidos",
    HUMAN_REVIEW_REQUIRED: "revisão humana necessária",
    DIRECT_EVIDENCE_REQUIRED: "faltam trechos de documentos inspecionados diretamente",
    PROVIDER_EXCERPT_ONLY: "apenas sínteses citadas da busca; páginas não inspecionadas",
    PARTIAL_PROVIDER_EXCERPTS: "parte do material é síntese citada da busca",
    LIMITED_INDEPENDENT_SOURCES: "poucas fontes independentes",
    QUESTION_NOT_RESOLVED: "a pesquisa ainda não delimitou o fato a medir",
    PARTIAL_COVERAGE: "resposta baseada nos elementos verificados; há detalhes adicionais não cobertos",
    ANSWER_OVERREACH: "a formulação da resposta exige cautela adicional",
    UNVERIFIED_COUNTEREVIDENCE: "há contraponto em síntese cuja página não pôde ser verificada",
    TARGET_ALIGNMENT: "o alvo avaliado não coincidiu com a afirmação enviada",
    CONCLUSION_ALIGNMENT: "a conclusão e a direção das evidências precisam de revisão",
  };

  const INDICADORES = {
    ESS: {
      nome: "Suporte das evidências",
      explicacao: "Mostra quanto as fontes apoiam os fatos avaliados. Levamos em conta o que cada fonte confirma ou contradiz, sua qualidade, relevância e compatibilidade com o caso. Quando há vários pontos comparáveis, os mais importantes pesam mais.",
    },
    ACS: {
      nome: "Qualidade da análise",
      explicacao: "Mostra quão bem a análise respondeu ao pedido. Considera a cobertura da pesquisa, a qualidade e a origem das fontes, a adequação ao contexto e a estabilidade da conclusão. Os pontos mais importantes da resposta pesam mais.",
    },
  };

  function metricasDaResposta(metricas) {
    return Object.keys(INDICADORES).map(id =>
      (Array.isArray(metricas) && metricas.find(m => m?.id === id)) || { id });
  }

  function adicionarMetricas(container, metricas, alvo = "") {
    const grupo = document.createElement("div"); grupo.className = "metricas-circulares";
    for (const m of metricasDaResposta(metricas)) {
      const indicador = INDICADORES[m.id];
      const valido = m.valid === true && typeof m.value === "number" && Number.isFinite(m.value) && m.value >= 0 && m.value <= 100;
      const limite = !valido && m.id === "ACS" && m.measurement === "upper_bound" && typeof m.upper_bound === "number" && Number.isFinite(m.upper_bound) && m.upper_bound >= 0 && m.upper_bound <= 100;
      const n = limite ? m.upper_bound : valido ? m.value : null;
      const item = document.createElement("div"); item.className = "veredito-metrica";
      const circulo = document.createElement("div");
      circulo.className = `metrica-circulo metrica-${m.id.toLowerCase()}${n === null ? " metrica-indisponivel" : ""}`;
      circulo.value = n;
      const cor = n === null ? "#94a3b8" : n < 40 ? "#dc4b4b" : n < 70 ? "#b88312" : "#26845b";
      circulo.style.background = `conic-gradient(${cor} ${(n ?? 0) * 3.6}deg, rgba(148,163,184,.22) 0deg)`;
      circulo.setAttribute("role", n === null ? "img" : "meter");
      const observado = m.id === "ESS" && m.measurement === "observed_support";
      const indeterminado = m.id === "ESS" && m.measurement === "undetermined_support";
      const provisorio = m.id === "ESS" && m.measurement === "provisional_direction";
      const alvoAvaliado = m.id === "ESS" && alvo ? ` para ${alvo}` : "";
      circulo.setAttribute("aria-label", `${indicador.nome}${alvoAvaliado}. ${n === null ? "Indisponível" : `${limite ? "No máximo " : ""}${n} de 100`}`);
      if (n !== null) {
        circulo.setAttribute("aria-valuemin", "0"); circulo.setAttribute("aria-valuemax", "100"); circulo.setAttribute("aria-valuenow", String(n));
      }
      const valor = document.createElement("strong");
      valor.textContent = n === null ? "—" : `${limite ? "≤ " : ""}${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}`;
      const centro = document.createElement("div"); centro.className = "metrica-circulo-centro";
      centro.appendChild(valor);
      const escala = document.createElement("small"); escala.textContent = n === null ? "Indisponível" : "%";
      centro.appendChild(escala); circulo.appendChild(centro); item.appendChild(circulo);
      const rotulo = document.createElement("div"); rotulo.className = "metrica-titulo";
      const nome = document.createElement("strong"); nome.textContent = indicador.nome;
      rotulo.appendChild(nome);
      const informacao = document.createElement("details"); informacao.className = "metrica-informacao";
      const icone = document.createElement("summary"); icone.textContent = "i";
      icone.setAttribute("aria-label", `Como é medido: ${indicador.nome}`);
      const explicacao = document.createElement("p");
      explicacao.textContent = indicador.explicacao + " A escala vai de 0 a 100 e expressa um índice da análise.";
      informacao.appendChild(icone); informacao.appendChild(explicacao);
      rotulo.appendChild(informacao); item.appendChild(rotulo);
      const ajuda = document.createElement("small");
      ajuda.textContent = n === null ? (MOTIVOS[m.reason] || "medição não disponível")
        : indeterminado ? "As fontes não permitem determinar a direção"
        : provisorio ? "Medição provisória"
        : observado ? "Nenhuma confirmação localizada; o fato ainda pode ter ocorrido"
        : limite ? "Limite superior; a qualidade completa ainda não pôde ser medida"
        : m.measurement === "combined_direction" ? "Resumo dos pontos verificados"
        : m.id === "ACS" ? "" : n < 40 ? "Evidências contrárias à afirmação"
        : n < 60 ? "Suporte intermediário à afirmação" : "Evidências favoráveis à afirmação";
      if (ajuda.textContent) item.appendChild(ajuda);
      grupo.appendChild(item);
    }
    container.appendChild(grupo);
  }

  function adicionarFontes(container, veredito) {
    if (!Array.isArray(veredito.source_details) || !veredito.source_details.length) return;
    const detalhes = document.createElement("details"); detalhes.className = "analise-fontes";
    const titulo = document.createElement("summary"); titulo.textContent = "Análise das fontes";
    detalhes.appendChild(titulo);
    for (const fonte of veredito.source_details.slice(0, 32)) {
      const item = document.createElement("article"); item.className = "fonte-avaliada";
      const rotulo = document.createElement("strong");
      const direcao = fonte.stance > 0 ? "Sustenta a afirmação" : fonte.stance < 0 ? "Contradiz a afirmação" : "Neutra";
      rotulo.textContent = fonte.retrieval_kind === "provider_excerpt" ? `Síntese citada da busca · ${direcao}` : direcao;
      item.appendChild(rotulo);
      try {
        const url = new URL(fonte.url);
        if (["http:", "https:"].includes(url.protocol) && !url.username && !url.password) {
          const link = document.createElement("a"); link.href = url.href; link.textContent = fonte.title || url.hostname;
          link.target = "_blank"; link.rel = "noopener noreferrer"; item.appendChild(link);
        }
      } catch (_) { /* Invalid URLs are never rendered as links. */ }
      for (const texto of [fonte.quote, fonte.rationale]) {
        const p = document.createElement("p"); p.textContent = texto || ""; item.appendChild(p);
      }
      detalhes.appendChild(item);
    }
    container.appendChild(detalhes);
  }

  function adicionarCatalogo(container, fontes) {
    if (!Array.isArray(fontes) || !fontes.length) return;
    const vistos = new Set();
    fontes = fontes.filter((fonte) => {
      if (!['qualified', 'qualified_excerpt', 'cited'].includes(fonte.status)) return false;
      try {
        const url = new URL(fonte.url);
        for (const key of [...url.searchParams.keys()]) if (/^utm_/i.test(key) || ['fbclid','gclid','msclkid'].includes(key)) url.searchParams.delete(key);
        url.hash = ''; url.searchParams.sort();
        const key = url.hostname.replace(/^www\./, '') + url.pathname.replace(/\/$/, '') + url.search;
        if (vistos.has(key)) return false;
        vistos.add(key); return true;
      } catch (_) { return false; }
    }).slice(0, 12);
    if (!fontes.length) return;
    const gaveta = document.createElement('details'); gaveta.className = 'catalogo-fontes';
    const titulo = document.createElement('summary'); titulo.textContent = `Principais fontes (${fontes.length})`;
    gaveta.appendChild(titulo);
    const estados = { qualified: 'Trecho avaliado', qualified_excerpt: 'Síntese avaliada · página não inspecionada', cited: 'Citada na resposta' };
    for (const fonte of fontes) {
      try {
        const url = new URL(fonte.url);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) continue;
        const linha = document.createElement('p'); linha.className = 'fonte-catalogo';
        const link = document.createElement('a'); link.href = url.href; link.textContent = fonte.title || url.hostname;
        link.target = '_blank'; link.rel = 'noopener noreferrer'; linha.appendChild(link);
        const estado = document.createElement('small'); estado.textContent = estados[fonte.status] || 'Fonte localizada';
        linha.appendChild(estado); gaveta.appendChild(linha);
      } catch (_) { /* No links from invalid schemes. */ }
    }
    container.appendChild(gaveta);
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
  function adicionarBolha(texto, tipo, anexos = []) {
    if (!areaConversa) return null;

    const bolha = document.createElement("div");
    bolha.className = `bolha bolha-${tipo}`;
    if (anexos.length) {
      const miniaturas = document.createElement("div");
      miniaturas.className = "imagens-prompt imagens-prompt-enviadas";
      miniaturas.append(...anexos.map(anexo => miniaturaImagem(anexo)));
      bolha.appendChild(miniaturas);
    }
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
  function adicionarRespostaIA(textoCru, promptOrigem, respostaFormatada = null, veredito = null, anexos = []) {
    if (!areaConversa) return null;

    const dados = parseRespostaIA(textoCru);
    const info = MAPA_VEREDICTO[veredito?.code];
    if (info) Object.assign(dados, info);
    if (veredito?.code === "INCONCLUSIVE" && veredito?.assessment_level === "preliminary") {
      dados.label = "Análise preliminar · evidências limitadas";
    }
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
    if (veredito?.mode === 'experimental' || veredito?.version === 2) {
      const modo = document.createElement('small'); modo.className = 'resposta-modo';
      modo.textContent = 'Modo complexo'; bloco.appendChild(modo);
    }

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
      if (veredito.retrieval) {
        const pesquisa = document.createElement('p'); pesquisa.className = 'pesquisa-resumo';
        const r = veredito.retrieval;
        const numero = (n) => Number.isInteger(n) && n >= 0 ? n : 0;
        pesquisa.textContent = `Pesquisa realizada: ${numero(r.queries_executed)} consultas · ${numero(r.sources_found)} fontes localizadas · ${numero(r.documents_available)} materiais avaliados`;
        painel.appendChild(pesquisa);
      }
      adicionarMetricas(painel, veredito.metrics, veredito.claim_details?.length === 1 ? veredito.claim_details[0].text : "");
      adicionarFontes(painel, veredito);
      adicionarCatalogo(painel, veredito.source_catalog);
      if (veredito.claim_details?.length) {
        const detalhes = document.createElement("details");
        const resumo = document.createElement("summary");
        resumo.textContent = "Alegações e limites da análise";
        detalhes.appendChild(resumo);
        for (const claim of veredito.claim_details.slice(0, 8)) {
          const item = document.createElement("div"); item.className = "metrica-alegacao";
          const titulo = document.createElement("p"); titulo.textContent = claim.text;
          item.appendChild(titulo);
          const estado = document.createElement("p");
          estado.textContent = (MAPA_VEREDICTO[claim.state]?.label || "Inconclusiva") +
            (claim.preliminary ? " · conclusão provisória" : "");
          item.appendChild(estado);
          if (claim.proof_basis === 'necessary_element_refuted') {
            const prova = document.createElement('p'); prova.className = 'metrica-nota';
            prova.textContent = 'Uma condição necessária da alegação foi diretamente contraditada. Não é preciso comprovar todos os detalhes históricos para refutá-la.';
            item.appendChild(prova);
          }
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
    } else if (veredito?.mode !== 'standard') {
      const nota = document.createElement("small");
      nota.className = "metrica-nota";
      nota.textContent = "Os indicadores não foram calculados nesta versão da resposta.";
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
    acoes.querySelector('[data-acao="copiar"]').addEventListener("click", async () => {
      const indicadores = veredito?.version === 2 ? "\n\n" + metricasDaResposta(veredito.metrics).map((m) =>
        `${INDICADORES[m.id].nome}: ${m.valid && typeof m.value === "number" ? `${m.value}%` :
          m.measurement === "upper_bound" && typeof m.upper_bound === "number" ? `≤ ${m.upper_bound}% (limite superior)` : "indisponível"}`).join("\n") : "";
      try {
        if (!navigator.clipboard?.writeText) throw new Error("Clipboard indisponível");
        await navigator.clipboard.writeText((textoCru || "") + indicadores);
        mostrarFeedback("Resposta copiada.", "success");
      } catch {
        mostrarFeedback("Não foi possível copiar a resposta. Verifique a permissão do navegador e tente novamente.");
      }
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
      reenviarPrompt(promptOrigem, anexos);
    });

    areaConversa.appendChild(bloco);
    areaConversa.scrollTop = areaConversa.scrollHeight;
    return bloco;
  }

  /* ── Auto-resize textarea ── */
  textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";

    if (editandoRascunhoLogin) {
      if (textarea.value.trim()) sessionStorage.setItem(chaveRascunhoLogin, textarea.value);
      else {
        sessionStorage.removeItem(chaveRascunhoLogin);
        editandoRascunhoLogin = false;
      }
    }
    atualizarCompositor();
    window.dispatchEvent(new Event("aleteia:chat-idle"));
  });

  /* ── Enter envia (Shift+Enter = nova linha) ── */
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!btnEnviar.disabled) enviarMensagem();
    }
  });

  btnEnviar.addEventListener("click", () => {
    if (requisicaoAtiva) {
      cancelarGeracao();
      textarea.focus();
      window.dispatchEvent(new Event("aleteia:chat-idle"));
    } else if (!btnEnviar.disabled) enviarMensagem();
  });

  /* ── Envia um prompt específico à API e renderiza a resposta ── */
  async function chamarApiEExibir(prompt, anexos = []) {
    if (requisicaoAtiva || chatBloqueado) return;
    const controle = new AbortController();
    requisicaoAtiva = controle;
    const mode = modeloSelecionado;
    bloquearModelo(true);
    const idDaConversa = conversaId;
    atualizarCompositor();
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

    controle.signal.addEventListener("abort", () => {
      loadingBubble.remove();
      if (!texto.trim()) {
        parcial.remove();
      } else if (!concluida) {
        parcial.className = "resposta-ia resposta-incompleta";
        const aviso = document.createElement("p");
        aviso.textContent = "Resposta cancelada.";
        parcial.insertBefore(aviso, corpoParcial);
      }
    }, { once: true });

    try {
      const res = await chamarApi("/api/chat/mensagem", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream"
        },
        body: JSON.stringify({
          conversa_id: idDaConversa, prompt, mode,
          ...(anexos.length ? { images: anexos.map(anexo => anexo.url) } : {})
        }),
        signal: controle.signal
      }, () => sessionStorage.setItem(chaveRascunhoLogin, prompt));

      if (controle.signal.aborted) return;
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
          adicionarRespostaIA(evento.resposta, prompt, evento.resposta_formatada, evento.veredito, anexos);
        }
      });
      if (controle.signal.aborted) return;
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
        bloquearModelo(false);
        atualizarCompositor();
        textarea.focus();
        window.dispatchEvent(new Event("aleteia:chat-idle"));
      }
    }
  }

  /* ── Reenvia um prompt já existente (usado pelo botão "Gerar novamente") ── */
  function reenviarPrompt(prompt, anexos) {
    chamarApiEExibir(prompt, anexos);
  }

  /* ── Enviar prompt digitado pelo usuário ── */
  async function enviarMensagem() {
    if (requisicaoAtiva || chatBloqueado || btnEnviar.disabled) return;
    const anexos = imagens.slice();
    const prompt = textarea.value.trim() || "Verifique as notícias ou alegações visíveis nas imagens.";

    if (editandoRascunhoLogin) {
      sessionStorage.removeItem(chaveRascunhoLogin);
      editandoRascunhoLogin = false;
    }
    ativarLayoutDeConversa();
    adicionarBolha(prompt, "usuario", anexos);
    ultimoPromptEnviado = prompt;

    textarea.value = "";
    textarea.style.height = "auto";
    limparImagensPrompt();

    await chamarApiEExibir(prompt, anexos);
  }

  /* ── Reabrir uma conversa antiga (chamado pelo main.js ao clicar na sidebar) ── */
  window.carregarConversa = async function (idConversa) {
    if (!areaConversa) return;
    cancelarGeracao();

    try {
      const res = await chamarApi(`/api/chat/conversas/${idConversa}`);
      if (!res.ok) return;

      const data = await res.json();

      if (conversaId !== idConversa) limparImagensPrompt();
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
    limparImagensPrompt();
    if (editandoRascunhoLogin) {
      sessionStorage.removeItem(chaveRascunhoLogin);
      editandoRascunhoLogin = false;
    }
    atualizarCompositor();
    textarea.focus();
  };

  window.addEventListener("conversaApagada", ({ detail: idConversa }) => {
    if (idConversa === conversaId) window.iniciarNovaConversa();
  });

  carregarConversaDaUrl();

  authPronta.then((usuario) => {
    const rascunho = sessionStorage.getItem(chaveRascunhoLogin);
    if (!usuario || !rascunho || textarea.value.trim() || requisicaoAtiva) return;
    editandoRascunhoLogin = true;
    textarea.value = rascunho;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });

  window.aleteiaColarSelecao = (text) => {
    if (requisicaoAtiva || chatBloqueado || textarea.value.trim()) return false;
    textarea.value = text;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.focus();
    return true;
  };

  /* ── Nova conversa ── */
  if (btnNovaConversa) {
    btnNovaConversa.addEventListener("click", (e) => {
      e.preventDefault();
      window.iniciarNovaConversa();
    });
  }

});
