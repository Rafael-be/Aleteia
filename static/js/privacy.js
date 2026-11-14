const STORAGE_KEY = "aleteiaPrivacyPreferences";
const validMeasurementId = (value) => /^G-[A-Z0-9]+$/i.test(value || "");

function readPreferences() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; }
}

function savePreferences(analytics) {
  const preferences = { version: 1, analytics: Boolean(analytics), updatedAt: new Date().toISOString() };
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences)); } catch { /* A escolha vale para a sessão atual. */ }
  return preferences;
}

function enableAnalytics() {
  const id = window.GA_MEASUREMENT_ID;
  if (window.__aleteiaAnalyticsLoaded || !validMeasurementId(id)) return;
  window.__aleteiaAnalyticsLoaded = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = (...args) => window.dataLayer.push(args);
  window.gtag("js", new Date());
  window.gtag("config", id, { anonymize_ip: true, allow_google_signals: false, allow_ad_personalization_signals: false });
  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  document.head.append(script);
}

function createControls() {
  const container = document.createElement("section");
  container.className = "privacy-consent";
  container.hidden = true;
  container.innerHTML = `
    <div class="privacy-consent__panel" role="dialog" aria-modal="true" aria-labelledby="privacyConsentTitle" aria-describedby="privacyConsentText">
      <h2 id="privacyConsentTitle">Sua privacidade</h2>
      <p id="privacyConsentText">Usamos armazenamento necessário para o funcionamento da conta. Com sua permissão, podemos usar métricas anônimas para melhorar a AleteIA.</p>
      <details class="privacy-consent__details"><summary>Personalizar preferências</summary><label><input type="checkbox" data-analytics> Permitir métricas de uso anônimas</label></details>
      <div class="privacy-consent__actions"><button type="button" data-reject>Rejeitar métricas</button><button type="button" data-save>Salvar preferências</button><button type="button" data-accept>Aceitar métricas</button></div>
      <a href="/privacidade">Leia a Política de Privacidade</a>
    </div>`;
  const settings = document.createElement("button");
  settings.type = "button";
  settings.className = "privacy-settings-toggle";
  settings.textContent = "Preferências de privacidade";
  document.body.append(container, settings);
  const checkbox = container.querySelector("[data-analytics]");
  const close = (analytics) => {
    const preferences = savePreferences(analytics);
    container.hidden = true;
    if (preferences.analytics) enableAnalytics();
    settings.focus({ preventScroll: true });
  };
  container.querySelector("[data-reject]").addEventListener("click", () => close(false));
  container.querySelector("[data-save]").addEventListener("click", () => close(checkbox.checked));
  container.querySelector("[data-accept]").addEventListener("click", () => close(true));
  settings.addEventListener("click", () => {
    const preferences = readPreferences();
    checkbox.checked = Boolean(preferences?.analytics);
    container.hidden = false;
    container.querySelector("[data-reject]").focus({ preventScroll: true });
  });
  return { container, checkbox };
}

document.addEventListener("DOMContentLoaded", () => {
  const preferences = readPreferences();
  const { container, checkbox } = createControls();
  if (preferences) {
    checkbox.checked = Boolean(preferences.analytics);
    if (preferences.analytics) enableAnalytics();
  } else {
    container.hidden = false;
    container.querySelector("[data-reject]").focus({ preventScroll: true });
  }
});
