import { SITE_URL } from "./config.js";

const site = new URL(SITE_URL);
if (site.protocol !== "https:" && !(site.protocol === "http:" && ["localhost", "127.0.0.1"].includes(site.hostname))) {
  throw new Error("Configure um domínio HTTPS ou um servidor local em config.js.");
}
const chatUrl = new URL("/chat?extension=1", site.origin).href;
const frame = document.getElementById("chat");
frame.src = chatUrl;
document.getElementById("reload").addEventListener("click", () => { frame.src = chatUrl; });
document.getElementById("open-site").addEventListener("click", () => {
  chrome.tabs.create({ url: new URL("/chat", site.origin).href });
});

const status = document.getElementById("selection-status");
const cancel = document.getElementById("cancel-selection");
const { id: windowId } = await chrome.windows.getCurrent();
let pending = null;
let lastError = "";
let loading = Promise.resolve();
function showStatus(message) {
  status.textContent = message;
  status.hidden = !message;
  cancel.hidden = !pending;
}
function refreshPending() {
  loading = loading.then(async () => {
    const items = await chrome.storage.session.get(null);
    const entries = Object.entries(items).filter(([key]) => key.startsWith(`selection:${windowId}:`));
    const expired = entries.filter(([, item]) => Date.now() - item.createdAt > 10 * 60 * 1000);
    if (expired.length) await chrome.storage.session.remove(expired.map(([key]) => key));
    const next = entries.filter((entry) => !expired.includes(entry))
      .sort((a, b) => a[1].createdAt - b[1].createdAt)[0];
    pending = next ? { key: next[0], ...next[1] } : null;
    if (!pending) { showStatus(lastError); return; }
    if (pending.error) {
      lastError = pending.error;
      showStatus(lastError);
      await chrome.storage.session.remove(pending.key);
      pending = null;
      return;
    }
    lastError = "";
    showStatus("Texto aguardando envio: entre na conta, confirme o e-mail e aguarde o chat ficar livre. Se houver um rascunho, envie ou apague-o.");
    frame.contentWindow.postMessage({ type: "aleteia:selection-ping" }, site.origin);
  }).catch(() => showStatus("Não foi possível preparar o texto. Selecione-o novamente."));
}
window.addEventListener("message", async (event) => {
  if (event.origin !== site.origin || event.source !== frame.contentWindow || !pending || pending.error) return;
  if (Date.now() - pending.createdAt > 10 * 60 * 1000) { refreshPending(); return; }
  if (event.data?.type === "aleteia:selection-ready") {
    frame.contentWindow.postMessage({ type: "aleteia:selection", id: pending.id, text: pending.text }, site.origin);
  }
  if (event.data?.type === "aleteia:selection-accepted" && event.data.id === pending.id) {
    const key = pending.key;
    pending = null;
    await chrome.storage.session.remove(key);
    refreshPending();
  }
});
frame.addEventListener("load", refreshPending);
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && Object.keys(changes).some((key) => key.startsWith(`selection:${windowId}:`))) refreshPending();
});
refreshPending();
cancel.addEventListener("click", async () => {
  lastError = "";
  pending = null;
  const items = await chrome.storage.session.get(null);
  await chrome.storage.session.remove(Object.keys(items).filter((key) => key.startsWith(`selection:${windowId}:`)));
  showStatus("");
});
