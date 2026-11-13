// Exercita o chat.js real com DOM mínimo, incluindo a transição delta -> done.
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import assert from "node:assert/strict";

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.listeners = {};
    this.value = "";
    this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  append(child) { this.appendChild(typeof child === "string" ? { textContent: child } : child); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute() {}
  querySelector() { return new Element(); }
  focus() {}
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((c) => c !== this); }
  replaceWith(child) {
    const index = this.parentNode.children.indexOf(this);
    child.parentNode = this.parentNode;
    this.parentNode.children.splice(index, 1, child);
  }
}
const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle"]
  .map((id) => [id, new Element()]));
let initialize;
let finish;
const gate = new Promise((resolve) => { finish = resolve; });
let started;
const streaming = new Promise((resolve) => { started = resolve; });
let ended;
const complete = new Promise((resolve) => { ended = resolve; });
const html = "<p><strong>Termo inicial</strong></p>\n<p><strong>Análise:</strong> Outro <strong>termo importante</strong>.</p>\n";
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");
vm.runInNewContext(source, {
  document: {
    addEventListener(type, fn) { initialize = fn; },
    getElementById(id) { return ids[id]; },
    createElement() { return new Element(); },
    createTextNode(text) { return { textContent: text }; },
  },
  window: { location: { search: "" }, addEventListener() {} },
  sessionStorage: { getItem() {}, setItem() {} },
  crypto: { randomUUID() { return "conversa"; } },
  URLSearchParams, AbortController, console, requestAnimationFrame: (callback) => callback(),
  chamarApi: async () => ({ ok: true }),
  consumirEventos: async (_, receber) => {
    receber({ type: "delta", text: "**Termo inicial**\n\n**Análise:** Outro **termo importante**.", html });
    started();
    await gate;
    receber({ type: "done", resposta: "**Termo inicial**\n\n**Análise:** Outro **termo importante**.\n\n**Veredicto:** FALSO",
      resposta_formatada: { corpo_html: html, analise_html: "<p>Outro <strong>termo importante</strong>.</p>" },
      veredito: { code: "FALSO", metrics: [] } });
    ended();
  },
});
initialize();
ids.promptInput.value = "Verifique isto";
ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click();
await streaming;
const area = ids.conversationArea;
const parcial = area.children.find((c) => c.className === "resposta-ia resposta-stream");
assert.equal(parcial.children[0].innerHTML, html, "Markdown precisa estar aplicado antes de done");
finish();
await complete;
const final = area.children.find((c) => c.className === "resposta-ia");
assert.equal(final.children[0].innerHTML, html, "Final deve preservar todo o conteúdo em negrito");
assert.equal(area.children.includes(parcial), false);
assert.equal(final.children.filter((c) => c.className === "veracidade-label").length, 1);
console.log("Interface: Markdown durante geração, conteúdo preservado e veredito único validados.");
