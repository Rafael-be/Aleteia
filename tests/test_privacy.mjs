import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const [privacy, observability, app, api, policy, main, chat, login, signup] = await Promise.all([
  readFile(new URL("../static/js/privacy.js", import.meta.url), "utf8"),
  readFile(new URL("../src/utils/observability.py", import.meta.url), "utf8"),
  readFile(new URL("../app.py", import.meta.url), "utf8"),
  readFile(new URL("../src/utils/api.py", import.meta.url), "utf8"),
  readFile(new URL("../public/privacidade.html", import.meta.url), "utf8"),
  readFile(new URL("../public/main/main-desktop.html", import.meta.url), "utf8"),
  readFile(new URL("../public/chat/chatIndex.html", import.meta.url), "utf8"),
  readFile(new URL("../public/login/login.html", import.meta.url), "utf8"),
  readFile(new URL("../public/cadastroTeste/cadastro.html", import.meta.url), "utf8"),
]);

assert.match(privacy, /const STORAGE_KEY = "aleteiaPrivacyPreferences"/);
assert.match(privacy, /if \(preferences\.analytics\) enableAnalytics\(\)/);
assert.match(privacy, /allow_google_signals: false/);
assert.match(privacy, /allow_ad_personalization_signals: false/);
assert.match(privacy, /data-reject/);
assert.match(privacy, /data-save/);
assert.match(observability, /SENTRY_DSN/);
assert.match(app, /GA_MEASUREMENT_ID/);
assert.match(api, /Permissions-Policy/);
assert.match(api, /www\.googletagmanager\.com/);
assert.match(policy, /Google Analytics 4 só são carregadas quando/);
for (const template of [main, chat, login, signup]) assert.match(template, /js\/privacy\.js/);
console.log("Privacidade: consentimento prévio, telemetria opcional e headers validados.");
