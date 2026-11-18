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
  setAttribute(name, value) { (this.attributes ??= {})[name] = value; }
  querySelector() { return new Element(); }
  focus() { this.focused = true; }
  contains(node) { return this === node || this.children.some((c) => c.contains?.(node)); }
  remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((c) => c !== this); }
}
const ids = Object.fromEntries(["promptInput", "btnEnviar", "conversationArea", "btnNovaConversa", "mainContent", "chatSubtitle", "seletorModelo", "botaoModelo", "nomeModelo", "menuModelos", "modeloBasico", "modeloExperimental", "avisoModoExperimental"]
  .map((id) => [id, new Element()]));
let initialize;
const documentListeners = {};
let finish;
const gate = new Promise((resolve) => { finish = resolve; });
let started;
const streaming = new Promise((resolve) => { started = resolve; });
let ended;
const complete = new Promise((resolve) => { ended = resolve; });
let scenario = "success";
const requests = [];
const html = "<p><strong>Termo inicial</strong></p>\n<p><strong>Análise:</strong> Outro <strong>termo importante</strong>.</p>\n";
const source = (await readFile(new URL("../static/js/chat.js", import.meta.url), "utf8"))
  .replace(/^import .*;\r?\n/gm, "");
vm.runInNewContext(source, {
  document: {
    addEventListener(type, fn) { if (type === 'DOMContentLoaded') initialize = fn; else documentListeners[type] = fn; },
    getElementById(id) { return ids[id]; },
    createElement() { return new Element(); },
    createTextNode(text) { return { textContent: text }; },
  },
  window: { location: { search: "" }, addEventListener() {} },
  sessionStorage: { getItem() {}, setItem() {} },
  crypto: { randomUUID() { return "conversa"; } },
  URL, URLSearchParams, AbortController, console, setTimeout, clearTimeout,
  chamarApi: async (_, options) => { if (options?.body) requests.push(JSON.parse(options.body)); return { ok: true }; },
  consumirEventos: async (_, receber) => {
    if (scenario === 'standard') {
      receber({ type: 'done', resposta: 'Texto simples.\n\n**Veredicto:** FALSO',
        resposta_formatada: { corpo_html: '<p>Texto simples.</p>' },
        veredito: { version: 1, code: 'FALSO', metrics: [], mode: 'standard' } });
      return;
    }
    if (scenario === 'search-without-support') {
      receber({ type: 'done', resposta: 'Não encontrei confirmação nas fontes consultadas.',
        resposta_formatada: { corpo_html: '<p>Não encontrei confirmação nas fontes consultadas.</p>' },
        veredito: { version: 2, code: 'NO_SUPPORT_FOUND', metrics: [
          { id: 'ESS', value: 0, valid: true, measurement: 'observed_support' },
          { id: 'ACS', value: 60, valid: true }],
          claim_details: [{ text: 'O streamer foi preso?' }] } });
      return;
    }
    if (scenario === 'contradicted-claim') {
      const metrics = [{ id: 'ESS', value: 12.4, valid: true }, { id: 'ACS', value: 90.5, valid: true }];
      receber({ type: 'done', resposta: 'Não foi estabelecida uma relação causal.',
        resposta_formatada: { corpo_html: '<p>Não foi estabelecida uma relação causal.</p>' },
        veredito: { version: 2, code: 'PREDOMINANTLY_CONTRADICTED', metrics,
          claim_details: [{ text: 'Paracetamol na gestação causa autismo no bebê?',
            state: 'PREDOMINANTLY_CONTRADICTED', metrics }],
          source_details: [{ stance: -0.5, title: 'Fonte avaliada', url: 'https://example.org',
            quote: 'Não foi estabelecida uma relação causal.', rationale: 'Não sustenta a alegação causal.' }],
          source_catalog: [{ url: 'https://example.org', title: 'Fonte avaliada', status: 'qualified' }] } });
      return;
    }
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
        source_catalog: [{ url: 'https://example.org', title: 'Fonte avaliada', status: 'qualified' },
                         { url: 'https://example.org/?utm_source=duplicate#citation', title: 'Duplicada', status: 'qualified' },
                         { url: 'https://other.example/report', title: 'Outra fonte', status: 'located' }],
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
assert.equal(ids.nomeModelo.textContent, 'Rápido', 'O seletor deve iniciar no modelo rápido');
assert.equal(ids.modeloBasico.attributes['aria-checked'], 'true');
assert.equal(ids.menuModelos.hidden, true);
assert.equal(ids.avisoModoExperimental.hidden, true);
ids.promptInput.value = "Verifique isto";
ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click();
await streaming;
assert.equal(requests[0].mode, 'standard');
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
const catalog = nodes.find((n) => n.className === 'catalogo-fontes');
assert.ok(catalog && catalog !== sources && catalog.open !== true,
  'Todas as fontes devem ter uma gaveta própria, separada das avaliações');
assert.ok(!descendants(catalog).some((n) => n.textContent === 'Outra fonte'), 'Fontes apenas localizadas não são principais');
assert.ok(!descendants(catalog).some((n) => n.textContent === 'Duplicada'), 'UTM e fragmentos não devem duplicar a fonte');
assert.ok(descendants(catalog).some((n) => n.textContent === 'Principais fontes (1)'));
assert.ok(nodes.some((n) => n.textContent === '%'), 'Indicadores devem mostrar percentuais');
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

scenario = 'contradicted-claim';
ids.promptInput.value = 'Paracetamol na gestação causa autismo no bebê?';
ids.btnEnviar.disabled = false; ids.btnEnviar.listeners.click(); await new Promise(setImmediate);
const contradicted = area.children.filter((c) => c.className === 'resposta-ia').at(-1);
const contradictedNodes = descendants(contradicted);
const ess = contradictedNodes.find((n) => n.className === 'metrica-circulo metrica-ess');
const acs = contradictedNodes.find((n) => n.className === 'metrica-circulo metrica-acs');
assert.equal(ess.value, 12.4, 'ESS baixo mede pouco apoio à hipótese causal original');
assert.equal(acs.value, 90.5, 'Uma resposta contrária à afirmação pode ter alta qualidade');
assert.ok(ess.attributes['aria-label'].includes('Paracetamol na gestação causa autismo no bebê?'),
  'O indicador deve identificar a hipótese avaliada, sem substituir o alvo pela resposta corrigida');
assert.ok(acs.attributes['aria-label'].includes('qualidade da análise'));
assert.ok(contradictedNodes.some((n) => n.textContent === 'Evidências contrárias à afirmação'));
assert.ok(contradictedNodes.some((n) => n.textContent === 'Predominantemente contraditada'));
assert.ok(contradictedNodes.some((n) => n.textContent === 'ESS mede a sustentação da afirmação avaliada; ACS, a qualidade da análise. Não são probabilidades calibradas.'));
assert.equal(contradictedNodes.filter((n) => n.className?.startsWith('metrica-circulo metrica-')).length, 2);
for (const name of ['analise-fontes', 'catalogo-fontes']) {
  assert.ok(contradictedNodes.find((n) => n.className === name)?.open !== true,
    'As fontes continuam recolhidas ao mostrar os indicadores');
}

scenario = 'search-without-support';
ids.promptInput.value = 'O streamer foi preso?';
ids.btnEnviar.disabled = false; ids.btnEnviar.listeners.click(); await new Promise(setImmediate);
const absentNodes = descendants(area.children.filter((c) => c.className === 'resposta-ia').at(-1));
assert.ok(absentNodes.some((n) => n.textContent === 'Sem sustentação nas fontes consultadas'));
assert.ok(absentNodes.some((n) => n.textContent === 'Nenhuma sustentação localizada; não significa falsidade comprovada'));
assert.ok(!absentNodes.some((n) => n.textContent === 'Evidências contrárias à afirmação'));
assert.equal(absentNodes.find((n) => n.className === 'metrica-circulo metrica-ess').value, 0);
assert.equal(absentNodes.find((n) => n.className === 'metrica-circulo metrica-acs').value, 60);

ids.botaoModelo.listeners.click();
assert.equal(ids.menuModelos.hidden, false);
assert.equal(ids.botaoModelo.attributes['aria-expanded'], 'true');
ids.menuModelos.listeners.keydown({ key: 'ArrowDown', target: ids.modeloBasico, preventDefault() {} });
assert.equal(ids.modeloExperimental.focused, true);
ids.modeloExperimental.listeners.click();
assert.equal(ids.nomeModelo.textContent, 'Complexo');
assert.equal(ids.modeloExperimental.attributes['aria-checked'], 'true');
assert.equal(ids.modeloBasico.attributes['aria-checked'], 'false');
assert.equal(ids.menuModelos.hidden, true);
assert.equal(ids.avisoModoExperimental.hidden, false, 'Ativar deve exibir o aviso experimental');
scenario = 'contradicted-claim';
ids.promptInput.value = 'Verificar no modo experimental'; ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click(); await new Promise(setImmediate);
assert.equal(requests.at(-1).mode, 'experimental');
assert.ok(descendants(area.children.filter((c) => c.className === 'resposta-ia').at(-1))
  .some((n) => n.className === 'resposta-modo' && n.textContent === 'Modo complexo'));

ids.botaoModelo.listeners.click();
ids.menuModelos.listeners.keydown({ key: 'Escape', target: ids.modeloExperimental, preventDefault() {} });
assert.equal(ids.menuModelos.hidden, true);
assert.equal(ids.nomeModelo.textContent, 'Complexo', 'Escape fecha sem alterar a escolha');
ids.botaoModelo.listeners.click();
documentListeners.click({ target: ids.promptInput });
assert.equal(ids.menuModelos.hidden, true, 'Clique fora deve fechar o seletor');
ids.botaoModelo.listeners.click();
ids.modeloBasico.listeners.click();
assert.equal(ids.nomeModelo.textContent, 'Rápido');
assert.equal(ids.avisoModoExperimental.classList.contains('visivel'), false);
scenario = 'standard';
ids.promptInput.value = 'Voltar ao modo padrão'; ids.btnEnviar.disabled = false;
ids.btnEnviar.listeners.click(); await new Promise(setImmediate);
assert.equal(requests.at(-1).mode, 'standard');
const standardNodes = descendants(area.children.filter((c) => c.className === 'resposta-ia').at(-1));
assert.ok(!standardNodes.some((n) => n.className === 'painel-indicadores'));
assert.ok(!standardNodes.some((n) => n.textContent === 'ESS e ACS não foram calculados nesta versão da resposta.'));
assert.ok(!standardNodes.some((n) => n.className === 'resposta-modo'));
