import { auth, chamarApi, sincronizarComBackend } from "./firebase-init.js";
import { deleteUser, onAuthStateChanged, sendEmailVerification, signOut } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

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
  document.body.style.visibility = "visible";
  document.body.style.opacity = "1";

  const conta = document.getElementById("btnConta");
  const contaMobile = document.getElementById("btnContaMobile");
  const overlay = document.getElementById("popupOverlay");
  const popup = document.getElementById("popupConta");
  const aviso = document.getElementById("avisoVerificacaoEmail");
  const reenviar = document.getElementById("btnReenviarVerificacao");
  const corrigirEmail = document.getElementById("btnCorrigirEmailVerificacao");
  const feedbackReenvio = document.getElementById("feedbackReenvioVerificacao");
  const emailPendente = document.getElementById("emailVerificacaoPendente");
  const abrir = () => { overlay?.classList.add("active"); popup?.classList.add("active"); };
  const fechar = () => { overlay?.classList.remove("active"); popup?.classList.remove("active"); };

  overlay?.addEventListener("click", fechar);
  document.getElementById("btnVoltar")?.addEventListener("click", fechar);
  document.getElementById("btnSair")?.addEventListener("click", async () => {
    await signOut(auth);
    window.location.href = "/";
  });
  reenviar?.addEventListener("click", async () => {
    const usuario = auth.currentUser;
    if (!usuario) return;
    reenviar.disabled = true;
    try {
      await sendEmailVerification(usuario);
      if (feedbackReenvio) feedbackReenvio.textContent = "E-mail de confirmação reenviado.";
    } catch {
      if (feedbackReenvio) feedbackReenvio.textContent = "Não foi possível reenviar agora. Tente novamente mais tarde.";
    } finally {
      reenviar.disabled = false;
    }
  });
  corrigirEmail?.addEventListener("click", async () => {
    const usuario = auth.currentUser;
    if (!usuario) return;
    corrigirEmail.disabled = true;
    try {
      await deleteUser(usuario);
      await signOut(auth);
      window.location.href = "/cadastro";
    } catch {
      if (feedbackReenvio) feedbackReenvio.textContent = "Para corrigir este e-mail, faça login novamente e tente outra vez.";
      corrigirEmail.disabled = false;
    }
  });

  // Responsabilidade: estado visual da conta e aviso de verificação.
  onAuthStateChanged(auth, async (usuario) => {
    verificacaoEmAndamento = null;
    const emailVerificado = await emailEstaVerificado(usuario);
    aviso?.classList.toggle("visivel", Boolean(usuario && !emailVerificado));
    if (emailPendente) emailPendente.textContent = usuario?.email || "";
    const chatBloqueado = Boolean(usuario && !emailVerificado);
    [document.getElementById("promptInput"), document.getElementById("btnEnviar")]
      .forEach((controle) => { if (controle) controle.disabled = chatBloqueado; });
    [document.getElementById("fotoConta"), document.getElementById("fotoContaMobile")]
      .forEach((foto) => { if (foto) foto.style.display = usuario ? "block" : "none"; });
    const acaoConta = () => usuario ? abrir() : (window.location.href = "/cadastro");
    conta?.addEventListener("click", acaoConta, { once: true });
    contaMobile?.addEventListener("click", acaoConta, { once: true });
    const nome = document.querySelector(".popup-username");
    if (usuario && nome) nome.textContent = `Olá, ${usuario.email}`;
  });

  window.adicionarItemNoAside = (chat) => {
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
      botaoExcluir.disabled = true;
      try {
        const resposta = await chamarApi(`/api/chat/conversas/${chat._id}`, { method: "DELETE" });
        if (!resposta?.ok) return;
        item.remove();
        // Remove também do cache local, para não reaparecer ao limpar a busca.
        conversasCompletas = conversasCompletas.filter((c) => c._id !== chat._id);
        window.dispatchEvent(new CustomEvent("conversaApagada", { detail: chat._id }));
      } catch (erro) {
        console.error("Não foi possível excluir a conversa:", erro);
      } finally {
        if (item.isConnected) botaoExcluir.disabled = false;
      }
    });
    item.append(texto, botaoExcluir);
    lista.prepend(item);

    // Mantém o cache local atualizado (evita duplicar quem já está nele).
    if (!conversasCompletas.some((c) => c._id === chat._id)) {
      conversasCompletas = [chat, ...conversasCompletas];
    }
  };

  const renderizarConversas = (conversas) => {
    const lista = document.getElementById("listaConversas");
    if (!lista) return;
    lista.replaceChildren();
    conversas.forEach(window.adicionarItemNoAside);
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
        if (!resposta?.ok || inputPesquisarConversas.value.trim() !== termo) return;
        renderizarConversas((await resposta.json()).prompts);
      } catch (erro) {
        console.error("Não foi possível pesquisar conversas:", erro);
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
        renderizarConversas(conversasCompletas);
      }
    } catch (erro) {
      console.error("Não foi possível preparar os dados da conta:", erro);
    }
  });
});