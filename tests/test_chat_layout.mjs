import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const css = await readFile(new URL("../static/css/chat.css", import.meta.url), "utf8");

assert.match(css, /#mainContent:not\(\.chat-ativo\) \.chat-header \{ width: 100%; \}/);
assert.match(css, /#mainContent:not\(\.chat-ativo\) \.chat-header > \.d-flex \{ width: 100%; justify-content: center !important; \}/);
assert.match(css, /#mainContent:not\(\.chat-ativo\) \.chat-header-subtitle \{ text-align: left; \}/);
assert.match(css, /\.menu-modelos\.menu-modelos--down \{ top: calc\(100% \+ \.65rem\); bottom: auto;/);
assert.match(css, /\.painel-indicadores \{[\s\S]*width: 100%;[\s\S]*max-width: none;[\s\S]*min-width: 0;/);
assert.match(css, /\.metricas-circulares \{[\s\S]*justify-content: center;[\s\S]*min-width: 0;/);
console.log("Layout do chat: cabeçalho mobile e indicadores matemáticos validados.");
