import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [app, main, chat, login, signup, notFound] = await Promise.all([
  readFile(new URL("../app.py", import.meta.url), "utf8"),
  readFile(new URL("../public/main/main-desktop.html", import.meta.url), "utf8"),
  readFile(new URL("../public/chat/chatIndex.html", import.meta.url), "utf8"),
  readFile(new URL("../public/login/login.html", import.meta.url), "utf8"),
  readFile(new URL("../public/cadastroTeste/cadastro.html", import.meta.url), "utf8"),
  readFile(new URL("../public/404.html", import.meta.url), "utf8"),
]);
const image = await readFile(new URL("../static/images/aleteia-share.jpg", import.meta.url));

assert.match(app, /@app\.route\("\/sitemap\.xml"\)/);
assert.match(app, /@app\.route\("\/robots\.txt"\)/);
assert.match(app, /urls = \(url_publica\("\/"\), url_publica\("\/extension"\)\)/);
assert.match(app, /APP_ENV", "development"/);
assert.match(app, /@app\.errorhandler\(404\)/);
assert.match(main, /og:image:width" content="1200"/);
assert.match(main, /twitter:card" content="summary_large_image"/);
assert.match(main, /rel="canonical"/);
for (const template of [chat, login, signup, notFound]) {
  assert.match(template, /name="robots" content="noindex,nofollow"/);
  assert.match(template, /rel="icon"/);
}
let offset = 2;
while (offset < image.length) {
  const marker = image.readUInt16BE(offset);
  const length = image.readUInt16BE(offset + 2);
  if (marker >= 0xffc0 && marker <= 0xffc3) {
    assert.equal(image.readUInt16BE(offset + 5), 630);
    assert.equal(image.readUInt16BE(offset + 7), 1200);
    break;
  }
  offset += length + 2;
}
assert.ok(offset < image.length, "JPEG deve conter um marcador de dimensões");
console.log("SEO: indexação, metadados, 404, sitemap, robots e imagem social validados.");
