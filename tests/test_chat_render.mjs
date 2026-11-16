// Exercita o chat.js real com DOM mínimo, incluindo a transição delta -> done.
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import assert from "node:assert/strict";

class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.listeners = {};
    this.value = "";
    this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  append(child) { this.appendChild(typeof child === "string" ? { textContent: child } : child); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  setAttribute() {}
  querySelector() { return new Element(); }
  focus() {}
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((c) => c !== this); }
}
const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle"]
  .map((id) => [id, new Element()]));
let initialize;
let finish;
const gate = new Promise((resolve) => { finish = resolve; });
let started;
const streaming = new Promise((resolve) => { started = resolve; });
let ended;
const complete = new Promise((resolve) => { ended = resolve; });
let scenario = "success";
const html = "<p><strong>Termo inicial</strong></p>\n<p><strong>Análise:</strong> Outro <strong>termo importante</strong>.</p>\n";
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");
vm.runInNewContext(source, {
  document: {
    addEventListener(type, fn) { initialize = fn; },
    getElementById(id) { return ids[id]; },
    createElement() { return new Element(); },
    createTextNode(text) { return { textContent: text }; },
  },
  window: { location: { search: "" }, addEventListener() {} },
  sessionStorage: { getItem() {}, setItem() {} },
  crypto: { randomUUID() { return "conversa"; } },
  URL, URLSearchParams, AbortController, console,
  chamarApi: async () => ({ ok: true }),
  consumirEventos: async (_, receber) => {
    if (scenario === 'scoped-success') {
      const metrics = (ess, acs) => [{ id: 'ESS', value: ess, valid: true }, { id: 'ACS', value: acs, valid: true }];
      receber({ type: 'done', resposta: 'Resposta por edição', resposta_formatada: { corpo_html: '<p>Resposta por edição</p>' },
        veredito: { version: 2, code: 'STRONGLY_SUPPORTED', scoped_metrics: true, metrics: [],
          claim_details: [{ text: '2019: cinema', context: '2019', state: 'STRONGLY_SUPPORTED', metrics: metrics(91, 71) },
                          { text: '2026: SUS', context: '2026', state: 'STRONGLY_SUPPORTED', metrics: metrics(95, 98) }] } });
      return;
    }
    if (scenario !== "success") {
      if (scenario === "partial-error") receber({ type: "delta", text: "Trecho parcial", html: "<p>Trecho parcial</p>" });
      receber({ type: "error", code: "provider_authentication_failed", message: "Configuração da IA recusada pelo provedor." });
      return;
    }
    receber({ type: "delta", text: "**Termo inicial**\n\n**Análise:** Outro **termo importante**.", html });
    started();
    await gate;
    receber({ type: "done", resposta: "**Termo inicial**\n\n**Análise:** Outro **termo importante**.\n\n**Veredicto:** FALSO",
      resposta_formatada: { corpo_html: html, analise_html: "<p>Outro <strong>termo importante</strong>.</p>" },
      veredito: { version: 2, code: "INCONCLUSIVE", assessment_level: "preliminary",
        retrieval: { queries_executed: 4, sources_found: 12, documents_available: 7 },
        source_details: [{ stance: 1, title: "Fonte pública", url: "https://example.org", quote: "<script>untrusted</script>", rationale: "Sustenta a alegação." }], metrics: [
        { id: "ESS", value: 68, valid: true },
        { id: "ACS", value: null, valid: false, reason: "DIMENSIONS_MISSING", upper_bound: 25, measurement: "upper_bound" },
      ], claim_details: [
        { text: "Alegação A", state: "PREDOMINANTLY_SUPPORTED", reasons: [], metrics: [
          { id: "ESS", value: 0, valid: true }, { id: "ACS", value: 80, valid: true },
        ] },
        { text: "Alegação B", state: "INCONCLUSIVE", reasons: ["INSUFFICIENT_EVIDENCE"], metrics: [
          { id: "ESS", value: "100", valid: true }, { id: "ACS", value: null, valid: false },
        ] },
      ] } });
    ended();
  },
});
initialize();
ids.promptInput.value = "Verifique isto";
ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click();
await streaming;
const area = ids.conversationArea;
const parcial = area.children.find((c) => c.className === "resposta-ia resposta-stream");
assert.equal(parcial.children[0].innerHTML, html, "Markdown precisa estar aplicado antes de done");
finish();
await complete;
const final = area.children.find((c) => c.className === "resposta-ia");
assert.equal(final.children[0].innerHTML, html, "Final deve preservar todo o conteúdo em negrito");
assert.equal(area.children.includes(parcial), false);
assert.equal(final.children.filter((c) => c.className === "veracidade-label").length, 1);
assert.ok(final.children.find((c) => c.className === "veracidade-label").children
  .some((c) => c.textContent === "Análise preliminar · evidências limitadas"),
  "Uma resposta fundamentada com pouco material deve ser identificada como preliminar");
const indicators = final.children.find((c) => c.className === "painel-indicadores");
assert.ok(indicators, "Indicadores precisam estar fora do corpo Markdown");
const descendants = (node) => [node, ...(node.children || []).flatMap(descendants)];
const nodes = descendants(indicators);
assert.ok(nodes.some((n) => n.className === "metrica-circulo metrica-ess" && n.value === 68));
assert.ok(nodes.some((n) => n.className === "metrica-circulo metrica-ess" && n.value === 0), "Zero válido não é ausência");
assert.ok(nodes.some((n) => n.textContent === "Indisponível"));
assert.ok(nodes.some((n) => n.textContent === "≤ 25"), "Um limite superior não pode ser exibido como score exato");
assert.equal(nodes.filter((n) => n.className?.startsWith("metrica-circulo metrica-") && !n.className.includes("indisponivel")).length, 4,
  "null e número em texto não podem preencher uma barra");
const sources = nodes.find((n) => n.className === "analise-fontes");
assert.ok(sources && sources.open !== true, "As avaliações de fontes devem começar recolhidas");
assert.ok(nodes.some((n) => n.className === "pesquisa-resumo" && n.textContent.includes("12 fontes")));
assert.ok(descendants(sources).some((n) => n.textContent === "<script>untrusted</script>"));
assert.ok(nodes.some((n) => n.className === "metrica-circulo metrica-ess" && n.style.background.startsWith("conic-gradient(")));
console.log("Interface: streaming Markdown, indicadores acessíveis e estados indisponíveis validados.");
await new Promise(setImmediate);
for (const mode of ["error", "partial-error"]) {
  scenario = mode;
  ids.promptInput.value = "Uma afirmação factual válida";
  ids.btnEnviar.disabled = false;
  ids.btnEnviar.listeners.click();
  await new Promise(setImmediate);
  assert.equal(area.children.filter((c) => c.className === "resposta-ia").length, 1,
    "Falha operacional não pode criar análise inconclusiva nem aviso de versão antiga");
  assert.ok(descendants(area).some((c) => c.textContent === "Configuração da IA recusada pelo provedor."));
}
assert.ok(area.children.some((c) => c.className === "resposta-ia resposta-incompleta"),
  "Texto parcial deve ser marcado como interrompido, sem veredito ou métricas");
scenario = 'scoped-success';
ids.promptInput.value = 'Pergunta com duas edições'; ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click(); await new Promise(setImmediate);
const scoped = area.children.filter((c) => c.className === 'resposta-ia').at(-1);
const scopedNodes = descendants(scoped);
assert.equal(scopedNodes.filter((n) => n.className === 'metricas-escopo').length, 2);
assert.equal(scopedNodes.filter((n) => n.className?.startsWith('metrica-circulo metrica-')).length, 4,
  'Cada escopo deve mostrar seus próprios círculos, sem média global ou duplicação nos detalhes');
assert.ok(scopedNodes.some((n) => n.textContent === '2019: cinema'));
assert.ok(scopedNodes.some((n) => n.textContent === '2026: SUS'));
