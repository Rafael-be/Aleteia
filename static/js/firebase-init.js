import { initializeApp } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js";
import { GoogleAuthProvider, OAuthProvider, createUserWithEmailAndPassword, getAuth, sendEmailVerification, signInWithEmailAndPassword, signInWithPopup } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

const firebaseConfig = window.FIREBASE_CONFIG;
if (!firebaseConfig?.apiKey || !firebaseConfig?.authDomain) throw new Error("FIREBASE_WEB_CONFIG_JSON não foi configurada.");
export const auth = getAuth(initializeApp(firebaseConfig));

export async function chamarApi(url, opcoes = {}) {
  const usuario = auth.currentUser;
  if (!usuario) { window.location.href = "/login"; return undefined; }
  const token = await usuario.getIdToken();
  return fetch(url, { ...opcoes, headers: { ...opcoes.headers, Authorization: `Bearer ${token}` } });
}

export async function sincronizarComBackend(usuario) {
  const resposta = await chamarApi("/api/auth/sincronizar", { method: "POST" });
  if (!resposta?.ok) throw new Error("Não foi possível sincronizar sua conta.");
  return usuario;
}

export async function cadastrarComEmail(email, senha) {
  const resultado = await createUserWithEmailAndPassword(auth, email, senha);
  await sendEmailVerification(resultado.user);
  return resultado.user;
}

export async function loginComEmail(email, senha) {
  const resultado = await signInWithEmailAndPassword(auth, email, senha);
  return resultado.user;
}

export async function loginSocial(provedor) {
  const providers = { google: new GoogleAuthProvider(), microsoft: new OAuthProvider("microsoft.com"), github: new OAuthProvider("github.com") };
  const resultado = await signInWithPopup(auth, providers[provedor]);
  return resultado.user;
}

window.cadastrarComEmail = cadastrarComEmail;
window.loginComEmail = loginComEmail;
