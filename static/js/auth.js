import { cadastrarComEmail, loginComEmail, loginSocial, destinoAposLogin } from "./firebase-init.js";
import { definirProcessamento, mensagemDeErro } from "./feedback.js";

const feedback = (element, mensagem, cor = "#e05555") => { element.textContent = mensagem; element.style.color = cor; element.style.display = "block"; element.setAttribute("role", "alert"); };
const mensagemAuth = (erro, fallback) => ({
  "auth/invalid-credential": "Não foi possível entrar na sua conta. Verifique suas credenciais e tente novamente.",
  "auth/wrong-password": "Não foi possível entrar na sua conta. Verifique suas credenciais e tente novamente.",
  "auth/user-not-found": "Não foi possível entrar na sua conta. Verifique suas credenciais e tente novamente.",
  "auth/email-already-in-use": "Este e-mail já está em uso. Entre na conta ou use outro endereço.",
  "auth/weak-password": "Escolha uma senha mais forte e tente novamente.",
  "auth/invalid-email": "Informe um endereço de e-mail válido.",
  "auth/too-many-requests": "Muitas tentativas foram feitas. Aguarde um momento e tente novamente.",
}[erro?.code] || mensagemDeErro(erro, fallback));
document.addEventListener("DOMContentLoaded", () => {
  const entrar = document.getElementById("btnEntrar"), cadastrar = document.getElementById("btnCadastrar");
  const dialogoEmailIncerto = document.getElementById("dialogoEmailIncerto");
  const textoEmailIncerto = document.getElementById("textoEmailIncerto");

  function confirmarEmailIncerto(email) {
    textoEmailIncerto.textContent = `Não conseguimos confirmar se o e-mail ${email} existe.`;
    dialogoEmailIncerto.showModal();
    return new Promise((resolver) => {
      const concluir = (continuar) => {
        dialogoEmailIncerto.close();
        if (!continuar) document.getElementById("email")?.focus();
        resolver(continuar);
      };
      document.getElementById("btnCorrigirEmailIncerto").onclick = () => concluir(false);
      document.getElementById("btnContinuarEmailIncerto").onclick = () => concluir(true);
      dialogoEmailIncerto.oncancel = (evento) => { evento.preventDefault(); concluir(false); };
    });
  }
  entrar?.addEventListener("click", async () => {
    const email = document.getElementById("inputEmail")?.value.trim(), senha = document.getElementById("inputSenha")?.value, aviso = document.getElementById("loginFeedback");
    if (!email || !senha) return feedback(aviso, "Preencha e-mail e senha.");
    definirProcessamento(entrar, true, "Entrando na conta");
    try { await loginComEmail(email, senha); window.location.href = destinoAposLogin; }
    catch (erro) { feedback(aviso, mensagemAuth(erro, "Não foi possível entrar na sua conta. Verifique suas credenciais e tente novamente.")); } finally { definirProcessamento(entrar, false); }
  });
  cadastrar?.addEventListener("click", async () => {
    const email = document.getElementById("email")?.value.trim(), senha = document.getElementById("password")?.value, confirmar = document.getElementById("confirm_password")?.value, aviso = document.getElementById("cadastroFeedback");
    if (!email || !senha || !confirmar) return feedback(aviso, "Preencha todos os campos.");
    if (senha !== confirmar) return feedback(aviso, "As senhas não coincidem.");
    definirProcessamento(cadastrar, true, "Criando conta");
    try {
      const usuario = await cadastrarComEmail(email, senha, () => confirmarEmailIncerto(email));
      if (usuario) window.location.href = destinoAposLogin;
    } catch (erro) {
      feedback(aviso, erro.code === "email_rejeitado" ? erro.message : mensagemAuth(erro, "Não foi possível criar a conta. Revise os dados e tente novamente."));
    } finally { definirProcessamento(cadastrar, false); }
  });
  document.querySelectorAll("[data-firebase-provider]").forEach((botao) => botao.addEventListener("click", async () => {
    if (botao.disabled) return;
    definirProcessamento(botao, true, "Conectando conta");
    try { await loginSocial(botao.dataset.firebaseProvider); window.location.href = destinoAposLogin; }
    catch (erro) { feedback(document.getElementById("loginFeedback"), mensagemAuth(erro, "Não foi possível entrar com este provedor. Tente novamente.")); }
    finally { definirProcessamento(botao, false); }
  }));
});
