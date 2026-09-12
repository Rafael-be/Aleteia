import { auth, chamarApi, sincronizarComBackend } from "./firebase-init.js";
import { onAuthStateChanged, sendEmailVerification, signOut } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

let verificacaoEmAndamento = null;

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
  const feedbackReenvio = document.getElementById("feedbackReenvioVerificacao");
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

  // Responsabilidade: estado visual da conta e aviso de verificação.
  onAuthStateChanged(auth, async (usuario) => {
    verificacaoEmAndamento = null;
    const emailVerificado = await emailEstaVerificado(usuario);
    aviso?.classList.toggle("visivel", Boolean(usuario && !emailVerificado));
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
    item.textContent = chat.prompt.slice(0, 40) + (chat.prompt.length > 40 ? "…" : "");
    item.dataset.id = chat._id;
    item.style.cursor = "pointer";
    item.addEventListener("click", () => window.carregarConversa?.(chat._id));
    lista.prepend(item);
  };

  // Responsabilidade: dados da aplicação; usuários não verificados não chamam a API.
  onAuthStateChanged(auth, async (usuario) => {
    if (!usuario || !await emailEstaVerificado(usuario)) return;
    try {
      await sincronizarComBackend(usuario);
      const resposta = await chamarApi("/api/chat/conversas");
      if (resposta?.ok) (await resposta.json()).prompts.forEach(window.adicionarItemNoAside);
    } catch (erro) {
      console.error("Não foi possível preparar os dados da conta:", erro);
    }
  });
});
