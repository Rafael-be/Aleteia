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
