# Aleteia Core V2 — implementação e operação

## O que está aplicado

O chat usa o pipeline em `src/services/analysis_service.py`, com cálculo puro em `src/core/scoring.py`. O prompt de sistema anterior foi substituído por extração e qualificação com contratos estruturados e rubricas limitadas. A explicação é montada por templates com trechos literais, citações clicáveis e a decisão calculada em Python. Não há chamada extra de redação nem números escolhidos livremente pelo modelo.

O código mantém a Responses API e o modelo definido por `OPENAI_MODEL` (padrão `gpt-5-mini`). São necessárias as permissões de busca web e saída estruturada nesse modelo/projeto. O backend só utiliza URLs expostas nos eventos de busca do provedor, e busca seus documentos com um cliente de rede restrito. A presença de links no texto do modelo não comprova busca.

O adaptador segue os contratos oficiais de [eventos e fontes da busca web](https://developers.openai.com/api/docs/guides/tools-web-search) e [saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). A biblioteca OpenAI continua fixada em `requirements.txt`; a conversão de schema usa o helper dessa versão.

Uma alegação factual usa até seis chamadas: extração, quatro recuperações com intenções distintas e qualificação em lote. Várias alegações compartilham extração/qualificação, mas cada alegação verificável recebe quatro recuperações. Com quatro alegações, o teto é dezoito chamadas e dezesseis buscas. A separação das intenções permite verificar a execução de cada uma e executar consultas em paralelo; há custo adicional frente ao chat simples. Não foi demonstrada economia em entradas factuais.

Entradas inequivocamente sem sentido usam zero chamadas de IA e resposta local curta. Perguntas curtas, siglas, fórmulas, idiomas diversos e referências ao histórico não são rejeitadas só por tamanho ou entropia. Entradas semanticamente fora de escopo ou sem contexto passam apenas pela extração, sem pesquisa posterior.

## Métricas e decisão

ESS: média geométrica SQ/R/CF com expoentes iguais, contribuição assinada e correção por dependência com γ=1; regularização `rho=0,20`; massa mínima `0,60`. Conflito usa `lambda_M=2`. Esses valores são **parâmetros candidatos de engenharia**, não resultados experimentais. Versão: `equal-weights-2026-11-v1`.

ACS usa cinco dimensões com pesos iguais. D utiliza validação de spans e auditoria semântica do qualificador; R usa intenções de recuperação executadas; E usa massa/cobertura/proveniência; C usa compatibilidade anotada; Rob mede sensibilidade numérica à remoção de grupos e perturbações de atributos. **Esses proxies não são recall humano nem robustez semântica validada.** Cada dimensão obrigatória desconhecida torna o ACS indisponível. Zero observado continua zero. Busca ou cobertura incompleta limita o ACS calculável a 50.

O limiar experimental de aceitação é ACS≥65; conflito ajustado≥0,45 exige massas opostas de grupos diferentes. ESS≥85 e ≥60 distingue sustentação forte/predominante; limites espelhados distinguem contradição. Verificabilidade, contexto, suficiência, criticidade e risco têm precedência. Casos de risco concreto exigem revisão humana, sem prometer serviço de revisão automático.

Origem desconhecida, atributos ausentes, omissão de elementos materiais ou busca incompleta bloqueiam ESS. Um trecho literal comprova presença textual, mas a relação lógica com a alegação ainda é uma anotação sujeita a erro. Fontes primárias são identificadas semanticamente; o sistema verifica referência literal e vínculos documentais, sem provar que todo documento é autêntico.

Domínios iguais, spans longos idênticos, textos próximos e cadeias documentais ligadas são agrupados conservadoramente. Conteúdo idêntico é deduplicado antes da qualificação. A mesma página tem uma unidade por alegação. Domínios diferentes não ganham independência automaticamente.

Para múltiplas alegações, o painel apresenta métricas individuais. Não publica uma média global sem comprovar comparabilidade e independência lógica. Uma alegação central contraditada não pode ser escondida por periféricas favoráveis. Cobertura incompleta bloqueia o resumo direcional global.

ESS/ACS são escalas de 0–100, **não probabilidades**. `null` aparece como “Indisponível”, acompanhado do motivo. As barras ficam fora do Markdown. Respostas antigas continuam legíveis, sem pontuações retroativas. O caminho JSON salva o mesmo resultado estruturado do SSE. A extensão embute `/chat`, portanto compartilha o painel e o contrato.

## Limites e custos

- Até quatro alegações, doze documentos distintos e 24.000 caracteres de evidência para qualificação; até doze trechos qualificados. Fontes inacessíveis e formatos não textuais não recebem conteúdo inventado.
- Janelas contíguas de texto são selecionadas por sobreposição temática; offsets e hashes registram exatamente o material inspecionado. Leitura parcial é marcada, e não equivale a inspeção integral da fonte.
- Cada chamada semântica tem teto de saída: 3.000 tokens para extração, 6.000 para qualificação; recuperação tem teto de 1.000. Tokens de raciocínio estão incluídos no orçamento de saída do provedor.
- Até dezoito chamadas, deadline de análise de 140 segundos e timeout de até 30 segundos por chamada. Callbacks do SDK registram o uso antes da validação semântica, inclusive quando a etapa seguinte falha.
- Após 48.000 tokens observados, o sistema não inicia novas chamadas. **Isso é um limite de interrupção observado, não um teto monetário rígido:** chamadas já em voo e contexto interno de busca podem excedê-lo. Configure também controles de orçamento no projeto do provedor.
- Até duas análises e quatro chamadas ao modelo simultâneas por processo. Cada análise tem até quatro tarefas paralelas de recuperação. Em múltiplos workers/réplicas, dimensionar os limites totais na infraestrutura.
- Cache em memória somente dos documentos recuperados sem autenticação/cookies, por URL, até 64 entradas e cinco minutos. Não há cache compartilhado de perguntas, histórico, decisões ou dados privados de usuários.

A requisição continua autenticada e sujeita ao rate limit atômico do Mongo. Ruído local devolve a quota de análise, preservando a contagem de tráfego por minuto. Uma execução que já tentou usar o provedor consome a quota mesmo se falhar ou for cancelada; isso evita retentativas ilimitadas com gasto. Falhas de transporte podem não expor contagem de tokens: não são reportadas como uso conhecido zero. A API não faz retries automáticos pagos.

O streaming informa etapas enquanto pesquisa e calcula. O corpo é transmitido em fragmentos somente depois da decisão, usando o mesmo renderizador de Markdown durante e após a geração. Não há transmissão de raciocínio interno ou indicadores parciais. Não se usa atraso artificial entre fragmentos.

Falhas operacionais não recebem veredito: autenticação do provedor, acesso ao modelo, conexão, limites e validação são reportados como erros próprios. O aviso de métricas não calculadas nesta versão é exclusivo de mensagens legadas concluídas. Se houver texto parcial antes de uma falha, a interface o marca como interrompido sem inventar classificação ou indicadores.

Se surgir `provider_authentication_failed`, confira `OPENAI_API_KEY` no processo do backend e no `.env` do projeto. Variáveis já exportadas pelo ambiente têm precedência sobre o arquivo. A credencial é da API do provedor, não o token Firebase do usuário. Após corrigir a configuração local, reinicie o backend. Não inclua valores de chaves em logs, mensagens ou capturas de tela.

Se a chave funciona em um processo novo, mas o Flask continua recusando após reinício, verifique exports antigos no terminal/IDE. O backend avisa quando `OPENAI_API_KEY`, `OPENAI_MODEL` ou `OPENAI_BASE_URL` herdados diferem do arquivo, sem registrar seus valores. Para iniciar localmente usando a chave e o modelo do `.env`, pare o servidor anterior e execute:

```bash
env -u OPENAI_API_KEY -u OPENAI_MODEL -u OPENAI_BASE_URL .venv/bin/python app.py
```

Isso limpa essas variáveis somente para o processo iniciado; não altera arquivos nem a precedência de configuração em produção.

## Segurança e retenção

Conteúdo de usuário, histórico e fontes não tem autoridade sobre parâmetros, scores ou ações. Contratos fechados rejeitam campos extras, números fora das rubricas, booleanos em atributos numéricos e dados ausentes disfarçados de score. URLs de fontes são limitadas aos resultados observados, e o servidor não usa cookies, proxies de ambiente ou credenciais para acessá-las.

O fetch valida hostname, esquema, porta e IPs de DNS; bloqueia redes internas/reservadas e endereços de metadata; fixa a conexão no IP público validado e verifica TLS com o hostname original. Revalida cada redirecionamento. Rejeita compressão e formatos não textuais; limita a resposta a 512 KB. Não executa JavaScript nem arquivos de fontes.

Esses controles reduzem riscos, mas não demonstram imunidade a injeção semântica ou falsificação documental. Manter egress da infraestrutura bloqueando redes internas e metadata como defesa adicional; servir o site por HTTPS no ambiente publicado.

Snapshots, atributos, consultas solicitadas/observadas, falhas, versões, uso e scores ficam em `analysis_audit` no mesmo documento Mongo da resposta. A gravação única evita resposta persistida sem seu dossiê. A auditoria não é retornada ao navegador nem usada como histórico do modelo. As consultas continuam segregadas pelo UID validado pelo Firebase; apagar a conversa também apaga o dossiê.

A auditoria recebe retenção de 30 dias. Para aplicar a exclusão dos snapshots vencidos **sem apagar o histórico**, agende:

```bash
python -m src.maintenance --purge-expired-audits
```

Esse comando precisa ser executado regularmente na infraestrutura; o campo de expiração sozinho não apaga dados. O índice opcional é preparado por `python -m src.maintenance --apply`, após revisar índices/dados. Não usar TTL no campo do chat, pois isso apagaria a mensagem inteira. Logs operacionais não incluem prompts, snapshots ou segredos.

## Instalação e validação

Atualize as dependências com `pip install -r requirements.txt` e reinicie o backend. Não há mudança de credenciais nem migração destrutiva do histórico. O contrato V2 é identificado por versão; registros legados usam apenas o parser antigo.

```bash
python -m unittest discover -s tests -v
node --test tests/*.mjs
```

Os testes usam provedores e rede simulados: exemplos do memorial, duplicação, baixa massa, inversão de direção, conflito, origem desconhecida, validação de trechos, SSRF, DNS, TLS, compressão, cache, uso em falhas, transporte JSON/SSE e DOM das barras durante/final do streaming. Os testes de concorrência real do Mongo exigem `AUDIT_TEST_MONGO_URI` apontando para banco descartável; não rodar contra produção.

Continuam necessárias a verificação com o provedor real, avaliação de navegadores reais e a campanha científica de anotação/calibração/teste independente. A implementação não prova superioridade, precisão ou economia frente a outra IA. Para a banca, descreva-a como implementação candidata auditável, com resultados empíricos ainda separados da formulação matemática.
