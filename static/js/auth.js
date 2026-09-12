import { cadastrarComEmail, loginComEmail, loginSocial } from "./firebase-init.js";

const feedback = (element, mensagem, cor = "#e05555") => { element.textContent = mensagem; element.style.color = cor; element.style.display = "block"; };
document.addEventListener("DOMContentLoaded", () => {
  document.body.style.visibility = "visible"; document.body.style.opacity = "1";
  const entrar = document.getElementById("btnEntrar"), cadastrar = document.getElementById("btnCadastrar");
  entrar?.addEventListener("click", async () => {
    const email = document.getElementById("inputEmail")?.value.trim(), senha = document.getElementById("inputSenha")?.value, aviso = document.getElementById("loginFeedback");
    if (!email || !senha) return feedback(aviso, "Preencha e-mail e senha.");
    entrar.disabled = true;
    try { await loginComEmail(email, senha); window.location.href = "/"; }
    catch { feedback(aviso, "Não foi possível fazer login. Confira seus dados."); } finally { entrar.disabled = false; }
  });
  cadastrar?.addEventListener("click", async () => {
    const email = document.getElementById("email")?.value.trim(), senha = document.getElementById("password")?.value, confirmar = document.getElementById("confirm_password")?.value, aviso = document.getElementById("cadastroFeedback");
    if (!email || !senha || !confirmar) return feedback(aviso, "Preencha todos os campos.");
    if (senha !== confirmar) return feedback(aviso, "As senhas não coincidem.");
    cadastrar.disabled = true;
    try { await cadastrarComEmail(email, senha); window.location.href = "/"; }
    catch { feedback(aviso, "Não foi possível criar a conta."); } finally { cadastrar.disabled = false; }
  });
  document.querySelectorAll("[data-firebase-provider]").forEach((botao) => botao.addEventListener("click", async () => {
    try { await loginSocial(botao.dataset.firebaseProvider); window.location.href = "/"; }
    catch { feedback(document.getElementById("loginFeedback"), "Não foi possível entrar com este provedor."); }
  }));
});
