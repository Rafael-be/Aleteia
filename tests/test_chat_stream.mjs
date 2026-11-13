import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

const source = await readFile(new URL("../static/js/chat-stream.js", import.meta.url), "utf8");
const { consumirEventos } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const encoder = new TextEncoder();
const payload = encoder.encode('data: {"type":"stage","message":"Análise e ação"}\r\n\r\ndata: {"type":"delta","text":"Olá"}\n\ndata: {"type":"done"}\n\n');
for (let size = 1; size <= payload.length; size++) {
  const stream = new ReadableStream({
    start(controller) {
      for (let i = 0; i < payload.length; i += size) controller.enqueue(payload.slice(i, i + size));
      controller.close();
    },
  });
  const received = [];
  await consumirEventos(new Response(stream), (event) => received.push(event));
  assert.deepEqual(received.map((e) => e.type), ["stage", "delta", "done"]);
  assert.equal(received[0].message, "Análise e ação");
  assert.equal(received[1].text, "Olá");
}
await assert.rejects(consumirEventos(new Response('data: {"type":"done"}'), () => {}));
const textoGrande = "resposta ".repeat(16_384);
const recebidoGrande = [];
await consumirEventos(new Response(`data: ${JSON.stringify({ type: "delta", text: textoGrande })}\n\ndata: {"type":"done"}\n\n`),
  (evento) => recebidoGrande.push(evento));
assert.equal(recebidoGrande[0].text, textoGrande);
console.log("SSE: fragmentação, UTF-8, CRLF, múltiplos eventos e truncamento validados.");
