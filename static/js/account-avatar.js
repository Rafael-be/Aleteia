const iconeUsuario = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></svg>';
const coresPorConta = new Map();

function corDaConta(usuario) {
  const chave = `aleteia:avatar:${usuario.uid || usuario.email}`;
  if (coresPorConta.has(chave)) return coresPorConta.get(chave);
  let cor;
  try { cor = localStorage.getItem(chave); } catch { /* Armazenamento indisponível. */ }
  if (!/^hsl\(\d{1,3}, 60%, 32%\)$/.test(cor || "")) {
    cor = `hsl(${Math.floor(Math.random() * 360)}, 60%, 32%)`;
    try { localStorage.setItem(chave, cor); } catch { /* Mantém a cor em memória. */ }
  }
  coresPorConta.set(chave, cor);
  return cor;
}

export function atualizarAvatares(usuario) {
  const email = usuario?.email?.trim() || "";
  const inicial = Array.from(email)[0]?.toLocaleUpperCase("pt-BR");
  const cor = usuario ? corDaConta(usuario) : "";
  document.querySelectorAll("[data-account-avatar]").forEach((avatar) => {
    if (usuario && inicial) avatar.textContent = inicial;
    else avatar.innerHTML = iconeUsuario;
    avatar.style.backgroundColor = cor;
    avatar.setAttribute("aria-label", usuario ? `Perfil de ${email || "usuário"}` : "Usuário deslogado");
  });
}
