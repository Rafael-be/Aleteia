import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const templates = await Promise.all([
  "../public/login/login.html",
  "../public/cadastroTeste/cadastro.html",
  "../public/main/main-desktop.html",
  "../public/chat/chatIndex.html",
].map((path) => readFile(new URL(path, import.meta.url), "utf8")));
const app = await readFile(new URL("../app.py", import.meta.url), "utf8");

for (const template of templates) {
  assert.doesNotMatch(template, /bootstrap\.bundle(?:\.min)?\.js/);
  assert.doesNotMatch(template, /js\/firebase-init\.js/);
  assert.match(template, /Montserrat:wght@100;300;400;500;600;700/);
}
assert.match(templates[0], /width="160" height="241"/);
assert.match(templates[2], /fetchpriority="high"/);
assert.match(app, /def asset_url\(filename\)/);
assert.match(app, /max-age=31536000, immutable/);
assert.match(app, /max-age=3600, must-revalidate/);
console.log("Performance: assets versionados, fontes restritas e scripts sem uso validados.");
