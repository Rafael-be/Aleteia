// A instalação não abre abas nem interrompe o trabalho do usuário.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
  .catch(console.error);
