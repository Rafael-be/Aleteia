import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../static/js/feedback.js", import.meta.url), "utf8");
const { lerErroDaResposta, mensagemDeErro } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
);

for (const status of [429, 502, 503]) {
  const erro = await lerErroDaResposta(new Response("indisponível", { status }));
  assert.equal(erro.status, status);
  assert.match(mensagemDeErro(erro), /solicitações|temporariamente indisponível/);
}

assert.match(mensagemDeErro(new TypeError("Failed to fetch")), /Verifique sua conexão/);
console.log("Feedback: respostas HTTP, proxy sem JSON e falha de conexão simulados e validados.");
