import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.listeners = {};
    this.attributes = {};
    this.classNames = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => this.classNames.add(name)),
      remove: (...names) => names.forEach((name) => this.classNames.delete(name)),
      toggle: (name, force) => { if (force === false) this.classNames.delete(name); else this.classNames.add(name); },
      contains: (name) => this.classNames.has(name),
    };
  }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name]; }
  querySelector(selector) { return this.parts?.[selector] || new Element(); }
  focus() {}
  contains(element) { return element === this || Object.values(this.parts || {}).includes(element); }
}

const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle", "seletorModelo", "botaoModelo", "nomeModelo", "menuModelos", "modeloBasico", "modeloExperimental", "avisoModoExperimental"]
  .map((id) => [id, new Element()]));
ids.avisoModoExperimental.parts = {
  ".aviso-modo-experimental-fechar": new Element(),
  ".aviso-modo-experimental-progresso": new Element(),
};
let initialize;
let nextTimer = 0;
const timers = new Map();
const setTimeoutFake = (fn, delay) => { const id = ++nextTimer; timers.set(id, { fn, delay }); return id; };
const clearTimeoutFake = (id) => timers.delete(id);
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");

vm.runInNewContext(source, {
  document: {
    addEventListener(type, listener) { if (type === "DOMContentLoaded") initialize = listener; },
    getElementById(id) { return ids[id]; },
    createElement() { return new Element(); },
    createTextNode(text) { return { textContent: text }; },
  },
  window: { location: { search: "" }, addEventListener() {} },
  sessionStorage: { getItem() {}, setItem() {} },
  crypto: { randomUUID: () => "conversa" },
  URL, URLSearchParams, AbortController, console,
  Date: { now: () => 1000 }, setTimeout: setTimeoutFake, clearTimeout: clearTimeoutFake,
  chamarApi: async () => ({ ok: true }), consumirEventos: async () => {},
});

initialize();
const aviso = ids.avisoModoExperimental;
const fechar = aviso.parts[".aviso-modo-experimental-fechar"];
assert.equal(aviso.hidden, true, "O aviso não aparece ao montar o seletor");

ids.modeloExperimental.listeners.click();
assert.equal(aviso.hidden, false, "A transição base para experimental exibe o aviso");
assert.equal(timers.size, 1, "Há um único temporizador de 15 segundos");
assert.equal([...timers.values()][0].delay, 15000);
assert.match(aviso.parts[".aviso-modo-experimental-progresso"].style.animation, /15000ms linear/);

ids.modeloExperimental.listeners.click();
assert.equal(timers.size, 1, "Reescolher experimental não duplica o aviso ou o timer");
aviso.listeners.mouseenter();
assert.equal(timers.size, 0, "Hover pausa a contagem");
aviso.listeners.mouseleave();
assert.equal(timers.size, 1, "Sair do hover retoma uma única contagem");

fechar.listeners.click();
assert.equal(aviso.classList.contains("visivel"), false, "O botão inicia o fechamento imediatamente sem mudar o modo");
assert.equal(ids.nomeModelo.textContent, "Complexo");
assert.equal(aviso.hidden, false, "O aviso permanece no layout durante a animação de saída");
const fechamento = [...timers.values()].find(({ delay }) => delay === 160);
fechamento.fn();
assert.equal(aviso.hidden, true, "O aviso é removido do layout após a saída");
ids.modeloBasico.listeners.click();
assert.equal(aviso.hidden, true, "Voltar ao básico mantém o aviso fechado");
ids.modeloExperimental.listeners.click();
const timer = [...timers.values()].find(({ delay }) => delay === 15000);
timer.fn();
assert.equal(aviso.hidden, false, "O temporizador inicia a animação de saída antes de ocultar o aviso");
const fechamentoAutomatico = [...timers.values()].find(({ delay }) => delay === 160);
fechamentoAutomatico.fn();
assert.equal(aviso.hidden, true, "O temporizador oculta o aviso após a animação de saída");

ids.modeloBasico.listeners.click();
const fechamentoAntigo = [...timers.values()].find(({ delay }) => delay === 160);
ids.modeloExperimental.listeners.click();
fechamentoAntigo.fn();
assert.equal(aviso.hidden, false, "Um fechamento antigo não oculta um aviso recém-exibido");
console.log("Aviso experimental: timer, pausa, fechamento e transições de modo validados.");
