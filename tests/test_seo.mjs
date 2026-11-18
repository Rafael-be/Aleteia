import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const [app, main, chat, login, signup, privacy, logo] = await Promise.all([
  readFile(new URL("../app.py", import.meta.url), "utf8"),
  readFile(new URL("../public/main/main-desktop.html", import.meta.url), "utf8"),
  readFile(new URL("../public/chat/chatIndex.html", import.meta.url), "utf8"),
  readFile(new URL("../public/login/login.html", import.meta.url), "utf8"),
  readFile(new URL("../public/cadastroTeste/cadastro.html", import.meta.url), "utf8"),
  readFile(new URL("../public/privacidade.html", import.meta.url), "utf8"),
  stat(new URL("../static/images/logo_Aleteia.png", import.meta.url)),
]);

assert.match(app, /@app\.route\("\/sitemap\.xml"\)/);
assert.match(app, /@app\.route\("\/robots\.txt"\)/);
assert.match(app, /share_image.*logo_Aleteia\.png/);
assert.match(app, /"title": "AleteIA"/);
assert.match(main, /og:image:width" content="500"/);
assert.match(main, /twitter:card" content="summary_large_image"/);
assert.match(main, /rel="canonical"/);
for (const template of [chat, login, signup, privacy]) {
  assert.match(template, /name="robots" content="noindex,nofollow"/);
  assert.match(template, /images\/logo-favicon\.png/);
}
assert.ok(logo.size > 0);
console.log("SEO: metadados sociais, páginas privadas, sitemap e assets visuais validados.");
