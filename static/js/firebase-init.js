import { initializeApp } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js";
import { GoogleAuthProvider, OAuthProvider, createUserWithEmailAndPassword, getAuth, onAuthStateChanged, sendEmailVerification, signInWithEmailAndPassword, signInWithPopup } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

const firebaseConfig = window.FIREBASE_CONFIG;
if (new URLSearchParams(window.location.search).get("extension") === "1" && window.self !== window.top) sessionStorage.setItem("aleteiaExtension", "1");
export const destinoAposLogin = sessionStorage.getItem("aleteiaExtension") === "1" ? "/chat" : "/";
if (!firebaseConfig?.apiKey || !firebaseConfig?.authDomain) throw new Error("Firebase configuration is missing.");
export const auth = getAuth(initializeApp(firebaseConfig));
const authPronta = new Promise((resolver) => onAuthStateChanged(auth, resolver));

function redirecionarParaLogin() {
  if (window.location.pathname !== "/login") window.location.replace("/login");
}

export async function chamarApi(url, opcoes = {}) {
  const usuario = auth.currentUser || await authPronta;
  if (!usuario) { redirecionarParaLogin(); return undefined; }
  return fetch(url, { ...opcoes, headers: { ...opcoes.headers, Authorization: `Bearer ${await usuario.getIdToken()}` } });
}

export async function sincronizarComBackend(usuario) {
  const resposta = await chamarApi("/api/auth/sincronizar", { method: "POST" });
  if (!resposta?.ok) {
    const detalhe = await resposta?.json().catch(() => ({}));
    const erro = new Error("Account synchronization failed.");
    erro.code = detalhe?.code;
    if (erro.code === "identity_recovery_required") window.dispatchEvent(new Event("aleteia:identity-recovery"));
    throw erro;
  }
  return usuario;
}

export async function migrarContaLegada(email, senha) {
  const headers = { "Content-Type": "application/json" };
  if (auth.currentUser) headers.Authorization = `Bearer ${await auth.currentUser.getIdToken()}`;
  return fetch("/api/auth/migrar-legado", { method: "POST", headers, body: JSON.stringify({ email, senha }) });
}

export async function validarEmailAntesDoCadastro(email) {
  try {
    const resposta = await fetch("/api/auth/validar-email", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
    return resposta.ok ? await resposta.json() : { status: "incerto", checagem_disponivel: false };
  } catch { return { status: "incerto", checagem_disponivel: false }; }
}

export async function cadastrarComEmail(email, senha, confirmarEmailIncerto) {
  const validacao = await validarEmailAntesDoCadastro(email);
  if (validacao.status === "rejeitado") { const erro = new Error("Email rejected."); erro.code = "email_rejeitado"; throw erro; }
  if (validacao.status === "incerto" && validacao.checagem_disponivel && !await confirmarEmailIncerto()) return null;
  const resultado = await createUserWithEmailAndPassword(auth, email, senha);
  await sendEmailVerification(resultado.user);
  return resultado.user;
}

export async function loginComEmail(email, senha) {
  try {
    const resultado = await signInWithEmailAndPassword(auth, email, senha);
    await migrarContaLegada(email, senha);
    return resultado.user;
  } catch (erroFirebase) {
    const migracao = await migrarContaLegada(email, senha);
    if (!migracao.ok) throw erroFirebase;
    return (await signInWithEmailAndPassword(auth, email, senha)).user;
  }
}

export async function loginSocial(provedor) {
  const providers = { google: new GoogleAuthProvider(), microsoft: new OAuthProvider("microsoft.com"), github: new OAuthProvider("github.com") };
  return (await signInWithPopup(auth, providers[provedor])).user;
}

window.cadastrarComEmail = cadastrarComEmail;
window.loginComEmail = loginComEmail;
