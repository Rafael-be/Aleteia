import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [style, auth, chat, main, feedback] = await Promise.all([
  readFile(new URL("../static/css/style.css", import.meta.url), "utf8"),
  readFile(new URL("../static/css/auth.css", import.meta.url), "utf8"),
  readFile(new URL("../static/css/chat.css", import.meta.url), "utf8"),
  readFile(new URL("../static/js/main.js", import.meta.url), "utf8"),
  readFile(new URL("../static/js/feedback.js", import.meta.url), "utf8"),
]);

assert.match(style, /button:not\(:disabled\):active[\s\S]*scale\(\.97\)/);
assert.match(style, /@keyframes feedback-success-pulse/);
assert.match(style, /@keyframes historico-entrada/);
assert.match(style, /prefers-reduced-motion: reduce[\s\S]*animation-duration/);
assert.match(auth, /var\(--radius-md\)/);
assert.match(chat, /var\(--radius-lg\)/);
assert.match(main, /evento\.key === "Escape"/);
assert.match(main, /animar && indice < 10/);
assert.match(main, /inserirNoTopo: false/);
assert.match(feedback, /tipo === "success"\) regiao\.classList\.add\("success-pulse"\)/);
console.log("Visual: movimentos reduzidos, pulso de sucesso, foco e stagger limitado validados.");
