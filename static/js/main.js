import { atualizarAvatares } from "./account-avatar.js";
import { auth, chamarApi, sincronizarComBackend } from "./firebase-init.js";
import { definirProcessamento, lerErroDaResposta, mensagemDeErro, mostrarFeedback } from "./feedback.js";
import { onAuthStateChanged, sendEmailVerification, signOut } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

let verificacaoEmAndamento = null;
let debouncePesquisaConversas = null;

/* ── Cache local com a lista completa (não filtrada) de conversas.
     Usado para restaurar a lista instantaneamente quando o campo de
     busca é esvaziado, sem depender de uma nova chamada à API. ── */
let conversasCompletas = [];

async function emailEstaVerificado(usuario) {
  if (!usuario) return false;
  if (!verificacaoEmAndamento) {
    verificacaoEmAndamento = usuario.reload()
      .then(() => usuario.emailVerified)
      .catch(() => usuario.emailVerified);
  }
  return verificacaoEmAndamento;
}

document.addEventListener("DOMContentLoaded", () => {
  const conta = document.getElementById("btnConta");
  const contaMobile = document.getElementById("btnContaMobile");
  const overlay = document.getElementById("popupOverlay");
  const popup = document.getElementById("popupConta");
  const aviso = document.getElementById("avisoVerificacaoEmail");
  const reenviar = document.getElementById("btnReenviarVerificacao");
  const corrigirEmail = document.getElementById("btnCorrigirEmailVerificacao");
  const feedbackReenvio = document.getElementById("feedbackReenvioVerificacao");
  const emailPendente = document.getElementById("emailVerificacaoPendente");
  const feedbackHistorico = document.getElementById("feedbackHistorico");
  let focoAntesDoPopup = null;
  const atualizarFeedbackHistorico = (mensagem = "", tipo = "") => {
    if (!feedbackHistorico) return;
    feedbackHistorico.textContent = mensagem;
    feedbackHistorico.dataset.tipo = tipo;
  };
  const abrir = () => {
    focoAntesDoPopup = document.activeElement;
    overlay?.classList.add("active");
    popup?.classList.add("active");
    document.getElementById("btnVoltar")?.focus({ preventScroll: true });
  };
  const fechar = (restaurarFoco = false) => {
    overlay?.classList.remove("active");
    popup?.classList.remove("active");
    if (restaurarFoco) focoAntesDoPopup?.focus?.({ preventScroll: true });
  };

  overlay?.addEventListener("click", () => fechar(true));
  document.getElementById("btnVoltar")?.addEventListener("click", () => fechar(true));
  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape" && popup?.classList.contains("active")) fechar(true);
  });
  document.getElementById("btnSair")?.addEventListener("click", async () => {
    try {
      await signOut(auth);
      window.location.href = "/";
    } catch (erro) {
      mostrarFeedback(mensagemDeErro(erro, "Não foi possível sair da conta. Tente novamente."));
    }
  });
  reenviar?.addEventListener("click", async () => {
    const usuario = auth.currentUser;
    if (!usuario) return;
    definirProcessamento(reenviar, true, "Reenviando e-mail de confirmação");
    try {
      await sendEmailVerification(usuario);
      if (feedbackReenvio) feedbackReenvio.textContent = "E-mail de confirmação reenviado.";
      mostrarFeedback("E-mail de confirmação reenviado.", "success");
    } catch {
      if (feedbackReenvio) feedbackReenvio.textContent = "Não foi possível reenviar agora. Tente novamente mais tarde.";
    } finally {
      definirProcessamento(reenviar, false);
    }
  });
  corrigirEmail?.addEventListener("click", () => {
    if (feedbackReenvio) {
      feedbackReenvio.textContent = "A alteração de e-mail não está disponível agora. Sua conta não foi alterada.";
    }
  });

  // Responsabilidade: estado visual da conta e aviso de verificação.
  onAuthStateChanged(auth, async (usuario) => {
    atualizarAvatares(usuario);
    verificacaoEmAndamento = null;
    const emailVerificado = await emailEstaVerificado(usuario);
    aviso?.classList.toggle("visivel", Boolean(usuario && !emailVerificado));
    if (emailPendente) emailPendente.textContent = usuario?.email || "";
    const chatBloqueado = Boolean(usuario && !emailVerificado);
    [document.getElementById("promptInput"), document.getElementById("btnEnviar")]
      .forEach((controle) => { if (controle) controle.disabled = chatBloqueado; });
    const acaoConta = () => usuario ? abrir() : (window.location.href = "/cadastro");
    if (conta) conta.onclick = acaoConta;
    if (contaMobile) contaMobile.onclick = acaoConta;
    const nome = document.querySelector(".popup-username");
    if (nome) nome.textContent = usuario ? `Olá, ${usuario.email || "usuário"}` : "Minha conta";
  });

  window.adicionarItemNoAside = (chat, { animar = false, indice = 0, inserirNoTopo = true } = {}) => {
    const lista = document.getElementById("listaConversas");
    if (!lista) return;
    const item = document.createElement("li");
    const texto = document.createElement("span");
    texto.textContent = chat.prompt.slice(0, 40) + (chat.prompt.length > 40 ? "…" : "");

    const botaoExcluir = document.createElement("button");
    botaoExcluir.className = "btn-excluir-conversa";
    botaoExcluir.type = "button";
    botaoExcluir.title = "Excluir conversa";
    botaoExcluir.setAttribute("aria-label", "Excluir conversa");
    botaoExcluir.innerHTML = `
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M9 7V4h6v3" />
        <path d="M6 7l1 13h10l1-13" />
        <g class="tampa-lixeira">
          <path d="M4 7h16" />
        </g>
      </svg>`;

    item.dataset.id = chat._id;
    if (animar && indice < 10) {
      item.classList.add("historico-entrada");
      item.style.setProperty("--historico-atraso", `${indice * 30}ms`);
    }
    item.style.cursor = "pointer";
    item.addEventListener("click", () => {
      if (window.carregarConversa) {
        window.carregarConversa(chat._id);
      } else {
        window.location.href = `/chat?conversa_id=${chat._id}`;
      }
    });
    botaoExcluir.addEventListener("click", async (event) => {
      event.stopPropagation();
      definirProcessamento(botaoExcluir, true, "Excluindo conversa");
      try {
        const resposta = await chamarApi(`/api/chat/conversas/${chat._id}`, { method: "DELETE" });
        if (!resposta?.ok) throw await lerErroDaResposta(resposta);
        item.remove();
        // Remove também do cache local, para não reaparecer ao limpar a busca.
        conversasCompletas = conversasCompletas.filter((c) => c._id !== chat._id);
        window.dispatchEvent(new CustomEvent("conversaApagada", { detail: chat._id }));
        mostrarFeedback("Conversa excluída.", "success");
      } catch (erro) {
        console.error("Não foi possível excluir a conversa:", erro);
        mostrarFeedback(mensagemDeErro(erro, "Não foi possível excluir a conversa. Tente novamente."));
      } finally {
        if (item.isConnected) definirProcessamento(botaoExcluir, false);
      }
    });
    item.append(texto, botaoExcluir);
    if (inserirNoTopo) lista.prepend(item);
    else lista.append(item);

    // Mantém o cache local atualizado (evita duplicar quem já está nele).
    if (!conversasCompletas.some((c) => c._id === chat._id)) {
      conversasCompletas = [chat, ...conversasCompletas];
    }
  };

  const renderizarConversas = (conversas, animar = false) => {
    const lista = document.getElementById("listaConversas");
    if (!lista) return;
    lista.replaceChildren();
    conversas.forEach((chat, indice) => window.adicionarItemNoAside(chat, { animar, indice, inserirNoTopo: false }));
    atualizarFeedbackHistorico(conversas.length ? "" : "Nenhuma conversa encontrada.", conversas.length ? "" : "empty");
  };

  const inputPesquisarConversas = document.getElementById("inputPesquisarConversas");
  inputPesquisarConversas?.addEventListener("input", () => {
    clearTimeout(debouncePesquisaConversas);
    const termo = inputPesquisarConversas.value.trim();

    // Campo de busca vazio: restaura a lista completa imediatamente a
    // partir do cache local, sem esperar nenhuma chamada à API. É isso
    // que garante que, ao apagar o texto, as conversas ocultas voltem
    // a aparecer na hora, mesmo que a rede esteja lenta ou falhe.
    if (!termo) {
      renderizarConversas(conversasCompletas);
      return;
    }

    debouncePesquisaConversas = setTimeout(async () => {
      try {
        const resposta = await chamarApi(`/api/chat/pesquisar?q=${encodeURIComponent(termo)}`);
        if (!resposta?.ok) throw await lerErroDaResposta(resposta);
        if (inputPesquisarConversas.value.trim() !== termo) return;
        renderizarConversas((await resposta.json()).prompts || []);
      } catch (erro) {
        console.error("Não foi possível pesquisar conversas:", erro);
        atualizarFeedbackHistorico(mensagemDeErro(erro, "Não foi possível pesquisar conversas. Tente novamente."), "error");
      }
    }, 300);
  });

  // Responsabilidade: dados da aplicação; usuários não verificados não chamam a API.
  onAuthStateChanged(auth, async (usuario) => {
    if (!usuario || !await emailEstaVerificado(usuario)) return;
    try {
      await sincronizarComBackend(usuario);
      const resposta = await chamarApi("/api/chat/conversas");
      if (resposta?.ok) {
        conversasCompletas = (await resposta.json()).prompts || [];
        renderizarConversas(conversasCompletas, true);
      } else throw await lerErroDaResposta(resposta);
    } catch (erro) {
      console.error("Não foi possível preparar os dados da conta:", erro);
      atualizarFeedbackHistorico(mensagemDeErro(erro, "Não conseguimos carregar suas conversas agora. Tente novamente em alguns instantes."), "error");
    }
  });
});
