import { auth, chamarApi } from "./firebase-init.js";
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

document.addEventListener("DOMContentLoaded", () => {
  document.body.style.visibility = "visible"; document.body.style.opacity = "1";
  const conta = document.getElementById("btnConta"), contaMobile = document.getElementById("btnContaMobile"), overlay = document.getElementById("popupOverlay"), popup = document.getElementById("popupConta");
  const abrir = () => { overlay?.classList.add("active"); popup?.classList.add("active"); };
  const fechar = () => { overlay?.classList.remove("active"); popup?.classList.remove("active"); };
  overlay?.addEventListener("click", fechar); document.getElementById("btnVoltar")?.addEventListener("click", fechar);
  document.getElementById("btnSair")?.addEventListener("click", async () => { await signOut(auth); window.location.href = "/"; });
  onAuthStateChanged(auth, (usuario) => {
    [document.getElementById("fotoConta"), document.getElementById("fotoContaMobile")].forEach((foto) => { if (foto) foto.style.display = usuario ? "block" : "none"; });
    const acaoConta = () => usuario ? abrir() : (window.location.href = "/cadastro");
    conta?.addEventListener("click", acaoConta, { once: true }); contaMobile?.addEventListener("click", acaoConta, { once: true });
    const nome = document.querySelector(".popup-username"); if (usuario && nome) nome.textContent = `Olá, ${usuario.email}`;
  });
  window.adicionarItemNoAside = (chat) => {
    const lista = document.getElementById("listaConversas"); if (!lista) return;
    const item = document.createElement("li"); item.textContent = chat.prompt.slice(0, 40) + (chat.prompt.length > 40 ? "…" : ""); item.dataset.id = chat._id; item.style.cursor = "pointer";
    item.addEventListener("click", () => window.carregarConversa?.(chat._id)); lista.prepend(item);
  };
  onAuthStateChanged(auth, async (usuario) => {
    if (!usuario) return;
    const resposta = await chamarApi("/api/chat/conversas"); if (!resposta?.ok) return;
    (await resposta.json()).prompts.forEach(window.adicionarItemNoAside);
  });
});
