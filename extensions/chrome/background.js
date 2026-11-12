// A instalação não abre abas nem interrompe o trabalho do usuário.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
  .catch(console.error);

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "aleteia-selection", title: "Enviar texto à AleteIA",
    contexts: ["selection"], documentUrlPatterns: ["http://*/*", "https://*/*"] });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "aleteia-selection" || !Number.isInteger(tab?.windowId)) return;
  const text = info.selectionText?.trim();
  if (!text) return;
  // Preserva o gesto do usuário: abrir antes de qualquer operação assíncrona.
  chrome.sidePanel.open({ windowId: tab.windowId }).catch(console.error);
  const id = crypto.randomUUID();
  chrome.storage.session.set({ [`selection:${tab.windowId}:${id}`]: {
    id, createdAt: Date.now(), text: text.length <= 12000 ? text : "",
    error: text.length > 12000 ? "Selecione um trecho menor: o limite é de 12.000 caracteres." : ""
  } }).catch(console.error);
});
chrome.windows.onRemoved.addListener((windowId) => {
  chrome.storage.session.get(null).then((items) => chrome.storage.session.remove(
    Object.keys(items).filter((key) => key.startsWith(`selection:${windowId}:`))
  )).catch(console.error);
});
