import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const code = (await readFile('static/js/extension-selection.js', 'utf8')).replace(/^import .*;\r?\n/gm, '');
const origin = `chrome-extension://${'a'.repeat(32)}`;
const parent = { postMessage: (...args) => messages.push(args) };
const messages = [], listeners = {}, sent = [];
const auth = { currentUser: { emailVerified: true } };
let busy = false;
const window = {
  ALETEIA_EXTENSION_IDS: ['a'.repeat(32)], parent,
  addEventListener: (type, fn) => { listeners[type] = fn; },
  aleteiaEnviarSelecao: (text) => { if (busy) return false; sent.push(text); return true; }
};
vm.runInNewContext(code, { window, auth, Set, JSON,
  sessionStorage: { getItem: () => null, setItem() {} },
  onAuthStateChanged: (_, fn) => fn()
});
const id = '12345678-1234-1234-1234-123456789abc';
const deliver = (data, overrides = {}) => listeners.message({ origin, source: parent, data, ...overrides });
const selection = { type: 'aleteia:selection', id, text: '<script>texto não confiável</script>' };
deliver(selection, { origin: 'https://evil.example' });
deliver(selection, { source: {} });
deliver({ ...selection, text: 'x'.repeat(12001) });
auth.currentUser = null;
deliver(selection);
auth.currentUser = { emailVerified: false };
deliver(selection);
assert.equal(sent.length, 0, 'recusa origem, janela, tamanho e autenticação inválidos');
auth.currentUser = { emailVerified: true };
busy = true;
deliver(selection);
assert.equal(messages.length, 0, 'não confirma recebimento enquanto ocupado');
busy = false;
deliver({ type: 'aleteia:selection-ping' });
assert.equal(messages.at(-1)[0].type, 'aleteia:selection-ready');
deliver(selection);
deliver(selection);
assert.deepEqual(sent, [selection.text], 'texto é passado sem interpretar HTML, sem duplicar envio');
assert.equal(messages.at(-1)[0].type, 'aleteia:selection-accepted');
assert.equal(messages.at(-1)[1], origin, 'respostas usam origem exata');

const background = await readFile('extensions/chrome/background.js', 'utf8');
let click, stored;
const calls = [];
vm.runInNewContext(background, { console, Date, crypto: { randomUUID: () => id }, chrome: {
  sidePanel: { setPanelBehavior: async () => {}, open: async () => { calls.push('open'); } },
  runtime: { onInstalled: { addListener() {} } },
  contextMenus: { onClicked: { addListener(fn) { click = fn; } } },
  windows: { onRemoved: { addListener() {} } },
  storage: { session: { set: async (value) => { calls.push('store'); stored = value; } } }
} });
click({ menuItemId: 'aleteia-selection', selectionText: 'Trecho selecionado', pageUrl: 'https://private.example/?secret=1' }, { windowId: 7 });
assert.deepEqual(calls, ['open', 'store'], 'abre dentro do gesto antes de armazenar');
assert.equal(stored[`selection:7:${id}`].text, 'Trecho selecionado');
assert.equal(JSON.stringify(stored).includes('private.example'), false, 'não armazena URL da página');
click({ menuItemId: 'aleteia-selection', selectionText: 'x'.repeat(12001) }, { windowId: 7 });
assert.equal(stored[`selection:7:${id}`].text, '', 'não armazena trechos acima do limite');
assert.ok(stored[`selection:7:${id}`].error);
console.log('Seleções: origem, remetente, autenticação, limite, duplicação e gesto validados.');
