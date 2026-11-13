import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.listeners = {};
    this.value = "";
    this.scrollHeight = 1000;
    this.clientHeight = 100;
    this.scrollTop = 0;
    const classes = new Set();
    this.classList = { add: (name) => classes.add(name), remove: (name) => classes.delete(name), toggle() {}, contains: (name) => classes.has(name) };
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  append(child) { this.appendChild(typeof child === "string" ? { textContent: child } : child); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute() {}
  querySelector() { return new Element(); }
  focus() {}
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((child) => child !== this); }
  replaceWith(child) {
    const index = this.parentNode.children.indexOf(this);
    child.parentNode = this.parentNode;
    this.parentNode.children.splice(index, 1, child);
  }
}

const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle"]
  .map((id) => [id, new Element()]));
let initialize;
let liberar;
const aguardar = new Promise((resolve) => { liberar = resolve; });
let iniciou;
const iniciado = new Promise((resolve) => { iniciou = resolve; });
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");

vm.runInNewContext(source, {
  document: {
    addEventListener(_, fn) { initialize = fn; },
    getElementById(id) { return ids[id]; },
    createElement() { return new Element(); },
    createTextNode(text) { return { textContent: text }; },
  },
  window: { location: { search: "" }, addEventListener() {} },
  sessionStorage: { getItem() {}, setItem() {} }, crypto: { randomUUID: () => "c" },
  URLSearchParams, AbortController, console, requestAnimationFrame: (callback) => callback(),
  chamarApi: async () => ({ ok: true }),
  definirProcessamento() {}, mensagemDeErro: (erro, fallback) => erro.mensagemSegura || fallback, mostrarFeedback() {},
  consumirEventos: async (_, receber) => {
    receber({ type: "delta", text: "texto parcial", html: "<p>texto parcial</p>" });
    iniciou();
    await aguardar;
    receber({ type: "done", resposta: "texto final", resposta_formatada: { corpo_html: "<p>texto final</p>" }, veredito: { code: "FALSO", metrics: [] } });
  },
});

initialize();
ids.promptInput.value = "pergunta";
ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click();
await iniciado;
ids.conversationArea.scrollTop = 0;
ids.conversationArea.listeners.scroll();
liberar();
await new Promise((resolve) => setTimeout(resolve, 0));

assert.equal(ids.conversationArea.scrollTop, 0, "a leitura manual não deve ser forçada ao fim");
assert.equal(ids.btnEnviar.disabled, true, "o campo vazio continua sem envio após concluir");
assert.equal(typeof ids.btnEnviar.listeners.click, "function");
assert.equal(ids.conversationArea.children.some((child) => child.className === "resposta-ia resposta-stream"), false);
assert.match(source, /controle\.signal\.aborted/);
assert.match(source, /cancelarGeracao\(\)/);
console.log("Chat: finalização substitui o parcial e preserva a rolagem manual.");
