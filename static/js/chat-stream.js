/* SSE via fetch: mantém o POST e o token Firebase, com leitura incremental UTF-8. */
export async function consumirEventos(response, receber) {
  if (!response.body) throw new Error("Streaming indisponível neste navegador.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const processar = (quadro) => {
    const dados = quadro.split(/\r?\n/).filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trimStart()).join("\n");
    if (dados) receber(JSON.parse(dados));
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let separador;
      while ((separador = /\r?\n\r?\n/.exec(buffer))) {
        processar(buffer.slice(0, separador.index));
        buffer = buffer.slice(separador.index + separador[0].length);
      }
      if (done) break;
    }
    if (buffer.trim()) throw new Error("Evento incompleto recebido.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
