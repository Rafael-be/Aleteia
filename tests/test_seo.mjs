import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const [app, main, chat, login, signup, privacy, favicon, share] = await Promise.all([
  readFile(new URL("../app.py", import.meta.url), "utf8"),
  readFile(new URL("../public/main/main-desktop.html", import.meta.url), "utf8"),
  readFile(new URL("../public/chat/chatIndex.html", import.meta.url), "utf8"),
  readFile(new URL("../public/login/login.html", import.meta.url), "utf8"),
  readFile(new URL("../public/cadastroTeste/cadastro.html", import.meta.url), "utf8"),
  readFile(new URL("../public/privacidade.html", import.meta.url), "utf8"),
  stat(new URL("../static/images/aleteia-favicon.png", import.meta.url)),
  stat(new URL("../static/images/aleteia-share.png", import.meta.url)),
]);

assert.match(app, /@app\.route\("\/sitemap\.xml"\)/);
assert.match(app, /@app\.route\("\/robots\.txt"\)/);
assert.match(app, /share_image.*aleteia-share\.png/);
assert.match(main, /og:image:width" content="1734"/);
assert.match(main, /twitter:card" content="summary_large_image"/);
assert.match(main, /rel="canonical"/);
for (const template of [chat, login, signup, privacy]) {
  assert.match(template, /name="robots" content="noindex,nofollow"/);
  assert.match(template, /aleteia-favicon\.png/);
}
assert.ok(favicon.size > 0 && share.size > 0);
console.log("SEO: metadados sociais, páginas privadas, sitemap e assets visuais validados.");
