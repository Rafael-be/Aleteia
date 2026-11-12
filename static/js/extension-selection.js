import { auth } from "./firebase-init.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-auth.js";

const origins = new Set((window.ALETEIA_EXTENSION_IDS || [])
  .map((id) => id.trim()).filter((id) => /^[a-p]{32}$/.test(id))
  .map((id) => `chrome-extension://${id}`));
let parentOrigin = null;
const accepted = new Set(JSON.parse(sessionStorage.getItem("aleteiaSelectionIds") || "[]"));
function ready() {
  if (parentOrigin && auth.currentUser?.emailVerified && window.aleteiaEnviarSelecao) {
    window.parent.postMessage({ type: "aleteia:selection-ready" }, parentOrigin);
  }
}
window.addEventListener("message", (event) => {
  if (window.parent === window || event.source !== window.parent || !origins.has(event.origin)) return;
  if (event.data?.type === "aleteia:selection-ping") {
    parentOrigin = event.origin;
    ready();
    return;
  }
  const { type, id, text } = event.data || {};
  if (type !== "aleteia:selection" || typeof id !== "string" || !/^[a-f0-9-]{36}$/.test(id)
      || typeof text !== "string" || !text.trim() || text.length > 12000 || !auth.currentUser?.emailVerified) return;
  if (!accepted.has(id)) {
    if (!window.aleteiaEnviarSelecao?.(text)) return;
    accepted.add(id);
    sessionStorage.setItem("aleteiaSelectionIds", JSON.stringify([...accepted].slice(-100)));
  }
  window.parent.postMessage({ type: "aleteia:selection-accepted", id }, event.origin);
});
onAuthStateChanged(auth, ready);
window.addEventListener("aleteia:chat-idle", ready);
