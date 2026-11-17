import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = (await readFile(new URL("../static/js/main.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");

class Element {
  constructor(rect = { left: 0, top: 0, width: 44, height: 44, bottom: 44 }) {
    this.rect = rect;
    this.visible = true;
    this.hidden = true;
    this.offsetWidth = 280;
    this.style = { setProperty: (name, value) => { this.style[name] = value; } };
    this.listeners = new Map();
    this.children = new Map();
  }

  getClientRects() { return this.visible ? [this.rect] : []; }
  getBoundingClientRect() { return this.rect; }
  querySelector(selector) { return this.children.get(selector) ?? null; }
  addEventListener(type, listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  trigger(type) { for (const listener of this.listeners.get(type) ?? []) listener({}); }
}

function criarContexto({ pathname = "/", storageThrows = false } = {}) {
  const desktop = new Element({ left: 900, top: 24, width: 44, height: 44, bottom: 68 });
  const mobile = new Element({ left: 250, top: 4, width: 44, height: 44, bottom: 48 });
  mobile.visible = false;
  for (const anchor of [desktop, mobile]) {
    const promo = new Element();
    const icon = new Element(anchor.rect);
    const close = new Element();
    anchor.children.set("[data-extension-promo]", promo);
    anchor.children.set("a", icon);
    anchor.children.set("[data-extension-promo-close]", close);
  }

  const documentListeners = new Map();
  const windowListeners = new Map();
  const document = {
    querySelectorAll: (selector) => selector === "[data-extension-promo-anchor]" ? [desktop, mobile] : [],
    querySelector: () => null,
    getElementById: () => null,
    addEventListener(type, listener) {
      documentListeners.set(type, [...(documentListeners.get(type) ?? []), listener]);
    },
    removeEventListener(type, listener) {
      documentListeners.set(type, (documentListeners.get(type) ?? []).filter((item) => item !== listener));
    },
  };
  const window = {
    location: { pathname },
    innerWidth: 1024,
    addEventListener(type, listener) {
      windowListeners.set(type, [...(windowListeners.get(type) ?? []), listener]);
    },
    removeEventListener(type, listener) {
      windowListeners.set(type, (windowListeners.get(type) ?? []).filter((item) => item !== listener));
    },
  };
  const saved = new Map();
  const sessionStorage = {
    getItem(key) {
      if (storageThrows) throw new Error("storage unavailable");
      return saved.get(key) ?? null;
    },
    setItem(key, value) {
      if (storageThrows) throw new Error("storage unavailable");
      saved.set(key, value);
    },
  };

  vm.runInNewContext(source, {
    document, window, sessionStorage, console,
    atualizarAvatares() {}, auth: {}, chamarApi() {}, sincronizarComBackend() {},
    onAuthStateChanged() {}, sendEmailVerification() {}, signOut() {},
    clearTimeout, setTimeout,
  });
  for (const listener of documentListeners.get("DOMContentLoaded") ?? []) listener();
  return {
    desktop, mobile, saved, documentListeners, windowListeners,
    resize() { for (const listener of windowListeners.get("resize") ?? []) listener(); },
    keydown(key) { for (const listener of documentListeners.get("keydown") ?? []) listener({ key }); },
  };
}

const contexto = criarContexto();
const promoDesktop = contexto.desktop.querySelector("[data-extension-promo]");
const promoMobile = contexto.mobile.querySelector("[data-extension-promo]");
assert.equal(promoDesktop.hidden, false, "exibe o aviso na âncora desktop visível");
assert.equal(promoMobile.hidden, true);
assert.equal(contexto.windowListeners.get("resize").length, 1, "registra apenas um listener de resize");

contexto.desktop.visible = false;
contexto.mobile.visible = true;
contexto.resize();
assert.equal(promoDesktop.hidden, true, "oculta o aviso da âncora anterior após trocar de breakpoint");
assert.equal(promoMobile.hidden, false, "exibe o aviso na âncora mobile visível");
assert.equal(promoMobile.style.top, "56px");

contexto.mobile.visible = false;
contexto.desktop.visible = true;
contexto.resize();
assert.equal(promoMobile.hidden, true, "oculta o aviso mobile ao retornar ao desktop");
assert.equal(promoDesktop.hidden, false, "restaura o aviso na âncora desktop visível");
assert.equal(contexto.windowListeners.get("resize").length, 1, "não duplica listeners durante transições");

contexto.desktop.querySelector("[data-extension-promo-close]").trigger("click");
assert.equal(promoDesktop.hidden, true, "fecha pelo botão");
assert.equal(contexto.saved.get("aleteiaExtensionPromoDismissed"), "true", "persiste a dispensa na sessão");
contexto.resize();
assert.equal(promoDesktop.hidden, true, "não reaparece após ser dispensado");

const contextoEscape = criarContexto();
contextoEscape.keydown("Escape");
assert.equal(contextoEscape.desktop.querySelector("[data-extension-promo]").hidden, true, "fecha com Escape");

const contextoSemStorage = criarContexto({ storageThrows: true });
contextoSemStorage.desktop.querySelector("[data-extension-promo-close]").trigger("click");
assert.equal(contextoSemStorage.desktop.querySelector("[data-extension-promo]").hidden, true, "fecha mesmo sem sessionStorage");

const contextoExtensao = criarContexto({ pathname: "/extension" });
assert.equal(contextoExtensao.desktop.querySelector("[data-extension-promo]").hidden, true, "não exibe o aviso em /extension");
assert.equal(contextoExtensao.windowListeners.get("resize"), undefined);

console.log("Callout: breakpoint, dispensa, Escape, storage indisponível e rota da extensão validados.");
