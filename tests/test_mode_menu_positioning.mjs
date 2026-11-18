import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Element {
  constructor() {
    this.style = { removeProperty(name) { delete this[name]; } };
    this.listeners = {};
    this.attributes = {};
    this.classes = new Set();
    this.classList = { add: (name) => this.classes.add(name), remove: (name) => this.classes.delete(name), toggle: (name, force) => force ? this.classes.add(name) : this.classes.delete(name), contains: (name) => this.classes.has(name) };
  }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  setAttribute(name, value) { this.attributes[name] = value; }
  querySelector() { return new Element(); }
  focus() {}
  contains(node) { return node === this; }
  getBoundingClientRect() { return this.rect; }
}
const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle", "seletorModelo", "botaoModelo", "nomeModelo", "menuModelos", "modeloBasico", "modeloExperimental", "avisoModoExperimental"].map((id) => [id, new Element()]));
ids.botaoModelo.rect = { top: 500, bottom: 540 };
ids.menuModelos.scrollHeight = 300;
const viewportListeners = {};
let initialize;
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8")).replace(/^import .*;\r?\n/gm, "");
vm.runInNewContext(source, {
  document: { addEventListener(type, listener) { if (type === "DOMContentLoaded") initialize = listener; }, getElementById: (id) => ids[id], createElement: () => new Element(), createTextNode: () => ({}) },
  window: {
    innerHeight: 568, location: { search: "" }, addEventListener() {}, removeEventListener() {},
    visualViewport: { offsetTop: 0, height: 568, addEventListener(type, listener) { viewportListeners[type] = listener; }, removeEventListener(type) { delete viewportListeners[type]; } },
  },
  sessionStorage: { getItem() {}, setItem() {} }, crypto: { randomUUID: () => "conversa" },
  URL, URLSearchParams, AbortController, console, setTimeout: () => 1, clearTimeout() {},
  chamarApi: async () => ({ ok: true }), consumirEventos: async () => {},
});
initialize();

ids.botaoModelo.listeners.click();
assert.equal(ids.menuModelos.classes.has("menu-modelos--down"), false, "Com espaço acima, o menu abre para cima");
assert.equal(ids.menuModelos.style.maxHeight, "492px");
ids.botaoModelo.listeners.click();
assert.equal(Object.keys(viewportListeners).length, 0, "Listeners temporários são removidos ao fechar");

ids.botaoModelo.rect = { top: 100, bottom: 140 };
ids.botaoModelo.listeners.click();
assert.equal(ids.menuModelos.classes.has("menu-modelos--down"), true, "Com pouco espaço acima, o menu abre para baixo");
assert.equal(ids.menuModelos.style.maxHeight, "420px");
ids.botaoModelo.listeners.click();

ids.botaoModelo.rect = { top: 300, bottom: 340 };
ids.menuModelos.scrollHeight = 750;
ids.botaoModelo.listeners.click();
assert.equal(ids.menuModelos.style.maxHeight, "292px", "Sem espaço suficiente, a altura é limitada ao espaço útil");
console.log("Seletor de modelos: posicionamento adaptativo e limpeza de listeners validados.");
