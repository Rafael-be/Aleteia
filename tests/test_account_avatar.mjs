import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const fonteAvatar = await readFile(new URL("../static/js/account-avatar.js", import.meta.url), "utf8");
const { atualizarAvatares } = await import(
  `data:text/javascript;base64,${Buffer.from(fonteAvatar).toString("base64")}`,
);
const fonteMain = await readFile(new URL("../static/js/main.js", import.meta.url), "utf8");

const armazenamento = new Map();
globalThis.localStorage = {
  getItem: (chave) => armazenamento.get(chave) ?? null,
  setItem: (chave, valor) => armazenamento.set(chave, String(valor)),
};

function criarAvatar() {
  return {
    textContent: "",
    innerHTML: "",
    style: { backgroundColor: "" },
    atributos: new Map(),
    setAttribute(chave, valor) { this.atributos.set(chave, valor); },
  };
}

const avatares = [criarAvatar(), criarAvatar(), criarAvatar()];
globalThis.document = { querySelectorAll: () => avatares };

atualizarAvatares({ uid: "u1", email: "ana@example.com" });
const cor = avatares[0].style.backgroundColor;
assert.match(cor, /^hsl\(\d{1,3}, 60%, 32%\)$/);
for (const avatar of avatares) {
  assert.equal(avatar.textContent, "A");
  assert.equal(avatar.style.backgroundColor, cor);
  assert.equal(avatar.atributos.get("aria-label"), "Perfil de ana@example.com");
}

atualizarAvatares({ uid: "u1", email: "ana@example.com" });
assert.equal(avatares[0].style.backgroundColor, cor);
atualizarAvatares(null);
for (const avatar of avatares) {
  assert.match(avatar.innerHTML, /<svg/);
  assert.equal(avatar.style.backgroundColor, "");
  assert.equal(avatar.atributos.get("aria-label"), "Usuário deslogado");
}

assert.doesNotMatch(fonteMain, /deleteUser/);
assert.doesNotMatch(fonteMain, /once:\s*true/);
assert.match(fonteMain, /atualizarAvatares\(usuario\)/);
assert.match(fonteMain, /conta\.onclick = acaoConta/);
console.log("Avatares, menu reabrível e fluxo não destrutivo validados.");
