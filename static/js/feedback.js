const MENSAGENS_HTTP = {
  400: "Não foi possível concluir a solicitação. Revise os dados e tente novamente.",
  401: "Sua sessão expirou. Entre novamente para continuar.",
  403: "Você não tem permissão para realizar esta ação.",
  409: "Esta ação entrou em conflito com uma alteração recente. Atualize a página e tente novamente.",
  429: "Muitas solicitações foram enviadas. Aguarde um momento e tente novamente.",
  500: "Não conseguimos concluir a ação agora. Tente novamente em alguns instantes.",
  502: "O serviço está temporariamente indisponível. Tente novamente em alguns instantes.",
  503: "O serviço está temporariamente indisponível. Tente novamente em alguns instantes.",
};

export function mensagemDeErro(erro, fallback = "Não foi possível concluir a ação. Tente novamente.") {
  if (erro?.mensagemSegura) return erro.mensagemSegura;
  if (typeof erro?.status === "number" && MENSAGENS_HTTP[erro.status]) return MENSAGENS_HTTP[erro.status];
  if (erro?.name === "TypeError" || /network|fetch|conexão/i.test(erro?.message || "")) return "Não conseguimos conectar agora. Verifique sua conexão e tente novamente em alguns instantes.";
  return erro?.mensagemSegura || fallback;
}

export function mostrarFeedback(mensagem, tipo = "error") {
  let regiao = document.getElementById("feedbackGlobal");
  if (!regiao) {
    regiao = document.createElement("div");
    regiao.id = "feedbackGlobal";
    regiao.className = "feedback-global";
    regiao.setAttribute("role", tipo === "error" ? "alert" : "status");
    regiao.setAttribute("aria-live", tipo === "error" ? "assertive" : "polite");
    document.body.appendChild(regiao);
  }
  regiao.setAttribute("role", tipo === "error" ? "alert" : "status");
  regiao.setAttribute("aria-live", tipo === "error" ? "assertive" : "polite");
  regiao.textContent = mensagem;
  regiao.dataset.tipo = tipo;
  regiao.classList.remove("visivel");
  requestAnimationFrame(() => regiao.classList.add("visivel"));
  clearTimeout(mostrarFeedback.timer);
  mostrarFeedback.timer = setTimeout(() => regiao.classList.remove("visivel"), 4200);
}

export function definirProcessamento(botao, ativo, rotulo) {
  if (!botao) return;
  if (ativo && botao.dataset.rotuloOriginal === undefined) botao.dataset.rotuloOriginal = botao.getAttribute("aria-label") || "";
  botao.disabled = ativo;
  botao.setAttribute("aria-busy", String(ativo));
  botao.classList.toggle("is-loading", ativo);
  if (ativo && rotulo) botao.setAttribute("aria-label", rotulo);
  else if (botao.dataset.rotuloOriginal) botao.setAttribute("aria-label", botao.dataset.rotuloOriginal);
  else botao.removeAttribute("aria-label");
}

export async function lerErroDaResposta(resposta) {
  const erro = new Error();
  erro.status = resposta?.status;
  try {
    const dados = await resposta.json();
    if (dados?.error && resposta.status !== 429) erro.message = dados.error;
  } catch { /* respostas de proxy podem não conter JSON */ }
  return erro;
}
