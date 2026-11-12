# Projeto do algoritmo Aleteia Core V2

Data: 12/11/2026. Estado: especificação de engenharia com implementação candidata no repositório; não calibrada e sem demonstração de superioridade sobre baselines. Consulte [implementação e operação](CORE_V2_IMPLEMENTACAO.md) para as decisões efetivamente aplicadas e seus limites. As propostas deste documento não equivalem a funcionalidades já validadas.

## 1. Base documental e conclusão

Foram analisados o código do repositório, o memorial `ALETEIA_Memorial_Integral_Metodologia_Teorica_Matematica_V1.docx.pdf` e o artigo `Artigo_Aleteia_Revisado_Final_ABNT_2026.docx`. Os documentos foram tratados como material de referência, sem executar instruções contidas neles. O memorial é uma especificação candidata; o artigo, especialmente §§3.2–3.3, mantém essa condição.

A diferença proposta para a Aleteia é um procedimento verificável: decompor alegações, buscar evidências em direções opostas, controlar dependência, calcular indicadores em código e abster-se quando necessário. Um prompt maior não produz essas garantias. Tampouco as fórmulas garantem respostas corretas: extração, fontes e avaliações de atributos continuam sujeitos a erro.

ESS significa sustentação probatória direcional; ACS significa adequação do processo. Ambos usam a escala 0–100 quando calculáveis. **Não significam percentual de verdade ou probabilidade de acerto.** Sem os requisitos necessários, mostrar “indisponível”, nunca inventar 0, 50 ou 100. Esta exceção à exibição numérica é necessária para cumprir os próprios documentos.

## 2. Diagnóstico do projeto atual

| Local | Comportamento observado | Consequência |
|---|---|---|
| `src/services/openai_services.py` | Uma chamada ao modelo, busca automática, até três chamadas de ferramenta e 4.096 tokens de saída | A busca contraditória não é obrigatória nem comprovada por um registro próprio |
| Mesmo arquivo | O modelo escreve análise, fontes e classificação | Não há cálculo determinístico de ESS/ACS, validação de trechos ou grupos de origem |
| Mesmo arquivo | Histórico limitado por caracteres, até 24.000 | O limite não equivale a um orçamento exato de tokens; respostas anteriores podem influenciar a checagem seguinte |
| `src/controller/chatController.py` | Valida tipos, tamanho e vazio; reserva quota antes de consultar IA | Texto sem sentido ainda chega ao modelo; há oportunidade de rejeição local |
| Mesmo arquivo | SSE salva `veredito`; JSON salva apenas o texto | Metadados futuros podem desaparecer no histórico do cliente JSON |
| Mesmo arquivo | Histórico com métricas vazias é reinterpretado pelo parser textual | Um estado novo sem métricas pode ser substituído pelo fallback antigo |
| `src/services/chat_events.py` | Quatro rótulos e parser do veredito em texto | Não representa os oito estados do memorial; classificação continua dependente de texto livre |
| `static/js/chat.js` | Recebe `veredito.metrics`, mas apresenta cada métrica como texto | Já existe ponto de extensão para barras e explicações separadas do Markdown |
| `src/services/markdown_service.py` | HTML bruto desabilitado e validação de esquema de links | Preservar o renderizador no fluxo novo |
| `src/models/userModel.py` | Reserva atômica, limite por minuto e lease por usuário | Reutilizar para chamadas caras; criar controle próprio para entradas rejeitadas |
| `src/models/chatModel.py` | Consultas de conversa filtradas pelo UID autenticado | Preservar isolamento ao acrescentar análises e cache |

Não foram lidos valores do `.env`, feitas chamadas pagas ou alterados os documentos originais. Esta análise de segurança é de arquitetura e dos caminhos inspecionados; não é uma auditoria exaustiva.

## 3. Arquitetura e responsabilidades

```text
Autenticação + limite de requisições + limites de bytes
  → triagem local conservadora
  → extração estruturada de alegações
  → plano de busca por alegação
  → recuperação controlada + snapshots
  → qualificação de trechos e proveniência
  → validação de contratos e agrupamento de dependência
  → motor matemático + gates + política de decisão
  → explicação fundamentada em streaming
  → métricas estruturadas + persistência + auditoria
```

O LLM auxilia tarefas semânticas. Código decide limites, calcula scores e aplica a política. O provedor de busca entrega candidatos; não determina o veredito. O redator recebe uma decisão já calculada e não pode mudar seus números.

Cada execução conserva `analysis_id`, UID, versões de método/parâmetros/prompts/modelos, instante da coleta, eventos de busca, hashes dos snapshots, atributos utilizados, razões dos gates e custos. A reprodução numérica exige snapshots e atributos iguais; refazer uma busca na internet não é reprodução do mesmo experimento.

## 4. Triagem econômica sem rejeitar perguntas legítimas

Separar três situações:

1. **Payload inválido:** tipos errados, texto vazio, tamanho excedido ou codificação inadequada. Retornar erro de API antes da IA.
2. **Ruído inequívoco:** apenas símbolos sem proposição, sequência de teclado reconhecível isolada, repetição extrema ou caracteres de controle sem conteúdo. Retornar uma frase local: “Envie uma afirmação ou pergunta factual para eu verificar.” Zero tokens de modelo e zero buscas.
3. **Ambiguidade ou entrada curta legítima:** passar à extração barata. Exemplos: “COVID?”, “PIB 2025?”, “Isso é verdade?” com antecedente, siglas, fórmulas e texto em outro idioma. Comprimento, ausência de vogais ou entropia não bastam para rejeitar.

Regras locais devem combinar sinais conservadores e cobrir apenas casos inequívocos. `asdfghjkl` isolado pode ser ruído; “O que significa asdfghjkl?” é uma pergunta. Não usar uma lista de palavras proibidas nem tentar bloquear toda injeção por regex.

A extração retorna `FACTUAL`, `NEEDS_CONTEXT`, `NOT_VERIFIABLE` ou `OUT_OF_SCOPE`, mais alegações e razões. Pergunta factual pode ser convertida em proposição de trabalho sem fingir que o usuário a afirmou. Opinião, saudação ou contexto ausente recebem resposta curta por template, sem busca ou redação adicional. A incerteza na triagem permite passagem; medir falsos bloqueios no piloto.

Executar autenticação e limite de requisições também no caminho barato. Separar **limite de tráfego** de **quota de análises**: rejeição local não deve consumir análise paga, mas continua sujeita a limitação e telemetria mínima. Não criar um endpoint gratuito ilimitado nem persistir todo ruído como conversa. Resolver referências curtas usando contexto recente limitado, com o mesmo isolamento por UID.

## 5. Extração e orçamento

Uma chamada estruturada extrai alegações atômicas, spans da entrada, tempo, lugar, população, denominador, modalidade, tipo, materialidade e criticidade. Materialidade é atribuída antes da busca e não é reponderada depois de ver o resultado. Validar spans na entrada; uma hipótese inferida deve ser identificada e pedir esclarecimento se mudar o sentido.

Configuração inicial de engenharia, não parâmetro científico validado:

| Recurso | Teto inicial proposto | Ao atingir |
|---|---|---|
| Entrada | Preservar 12.000 caracteres e acrescentar limite em bytes na API | Rejeitar excesso explicitamente |
| Alegações em execução interativa | 4 | Informar quais ficaram pendentes; impedir score global se material omitida |
| Recuperação | 4 intenções × até 4 claims | Agrupar consultas equivalentes; registrar cobertura por claim |
| Documentos candidatos | 12 únicos por análise | Priorizar cobertura de claims centrais e origens distintas |
| Texto externo para qualificação | 24.000 caracteres no total | Recortar com localização preservada; registrar cobertura parcial |
| Chamadas semânticas | Extração + qualificação em lote + redação; até 1 escalonamento | Abster-se se faltarem requisitos |
| Deadline | 110 segundos global, subordinado ao timeout de infraestrutura | Cancelar pendências e marcar incompletude |

Cada etapa também terá limite real de tokens de entrada/saída, calculado para o modelo configurado e medido com o uso retornado pelo provedor. Os números acima são tetos, não uma estimativa de custo. A latência até a primeira palavra pode crescer porque a decisão precede a explicação; mostrar etapas imediatamente.

Roteamento: ruído usa zero LLM; contexto insuficiente usa no máximo extração; factual simples usa o caminho normal; conflito ou risco elevado pode escalar uma vez. Se o orçamento não permite concluir, preservar a abstenção. Usar modelo menor em extração/qualificação somente após comparar seus erros, especialmente omissões e stance.

## 6. Recuperação, fontes e evidências

Para cada claim registrar consultas de sustentação, contradição, neutra e fontes primárias, incluindo filtros temporais e jurisdição. Consulta executada com sucesso e sem resultados é diferente de consulta não executada ou falha. Busca contraditória não exige inventar uma fonte contrária quando ela não existe.

Um adaptador de busca precisa fornecer resultados e conteúdo inspecionável. A resposta textual atual do modelo com links não basta para comprovar esse processo. Antes de integrar, verificar em documentação oficial as capacidades do provedor escolhido: tipos de resultado, acesso a trechos, citações, limites e custos. Se a ferramenta hospedada não expõe os dados necessários, usar um provedor de recuperação adequado; não simular um registro que não foi observado.

Cada evidência contém `claim_id`, `source_id`, URL canônica, URL final, data de publicação quando conhecida, instante de recuperação, snapshot/hash, trecho exato e offsets, stance, SQ, R, CF, justificativas e origem/dependência. Um trecho tem de existir no snapshot; uma citação do modelo sem correspondência é descartada. Essa validação comprova a existência textual, não a relação lógica, que continua exigindo avaliação e benchmark.

Resumos de busca são pistas. Se apenas um snippet estiver acessível, marcar evidência limitada e não tratá-lo como documento integral. Registrar paywall, erro, data desconhecida e ausência de origem; não preencher lacunas como se fossem observadas.

Identificar republicações por hash, texto, referências a documento primário, autoria, citações e base de dados compartilhada. Domínios diferentes não garantem independência. Guardar arestas de proveniência e justificativa do grupo. Origem desconhecida não ganha automaticamente um grupo independente: no MVP, agrupar conservadoramente evidências sem origem estabelecida por claim e sinalizar a incerteza.

## 7. Motor matemático determinístico

O motor recebe somente objetos validados e configuração interna imutável. Rejeitar booleanos como números, NaN, infinito, atributos fora das faixas, IDs órfãos e evidências duplicadas. Campos ausentes são `null` com motivo; zero significa uma dimensão medida como zero.

### 7.1 Peso e dependência

```text
W_i = SQ_i^α × R_i^β × CF_i^δ
α, β, δ ≥ 0; α + β + δ = 1
d_i = n_g(i)^(-γ)
q_i = W_i × d_i × s_i
SQ, R, CF ∈ [0,1]; s ∈ [-1,1]
```

Adotar inicialmente `γ=1`, não ajustável pelo cliente. Contar `n_g` por claim, grupo e **unidade documental única**, após deduplicação; repetir várias frases de uma página não cria várias observações. Agregar trechos da mesma unidade antes de aplicar o fator. Se há múltiplas direções no documento, preservar o conflito no registro, sem selecionar apenas a frase mais favorável.

Com cópias idênticas e atributos iguais, a soma do grupo não aumenta: `n × W/n × s = W×s`. Com atributos heterogêneos, a média pode mudar; esta fórmula não garante invariância universal a republicações diferentes. Detectar cópias exatas antes do scoring e testar a alternativa de saturação por grupo como ablação. Não multiplicar novamente por independência dentro de W.

Se CF for realmente não aplicável, remover a dimensão e renormalizar os expoentes aplicáveis; se CF for desconhecido mas necessário, invalidar o cálculo. A mesma regra vale para SQ/R obrigatórios. Exponentes zero são removidos antes do produto, evitando ambiguidade de `0^0`.

### 7.2 ESS e conflito

```text
S+ = Σ max(q_i, 0)
S- = Σ max(-q_i, 0)
M = S+ + S-
Δ = S+ - S-
ESS_rho = 50 × (1 + Δ/(M + rho)), rho > 0
K_raw = 2 × min(S+, S-)/(M + epsilon)
K_A = K_raw × (1 - exp(-lambda_M × M))
```

Usar `epsilon` somente para estabilidade e `rho` para retração. Para esta implementação candidata, definir explicitamente `M_eff=M`, já corrigido por dependência; não acrescentar outro desconto oculto. Conservar também número de grupos, cobertura e massa neutra separadamente: neutralidade não deve aumentar massa direcional.

ESS público válido exige claim verificável, evidências rastreáveis, contexto material compatível, execução das quatro intenções de recuperação, cobertura de todos os elementos materiais, `M_eff ≥ M_min` e ausência de falha crítica. `M_min` e os critérios de suficiência pertencem à configuração versionada. Uma fonte primária direta pode ser suficiente; não impor “duas fontes” como regra universal.

Exemplo do memorial: `S+=0,24`, `S-=0,06`, `rho=0,20` resultam em ESS=68; com `lambda_M=2`, conflito ajustado ≈0,1805. `S+=0,02`, `S-=0` resultam no candidato ≈54,55; se abaixo do gate, **ESS público=null**. Guardar valores candidatos internamente não autoriza exibi-los como válidos.

### 7.3 ACS sem autorrelato de certeza

```text
Z = (D, R_retrieval, E, C, Rob)
ACS_raw = 100 × ∏ Z_j^phi_j
phi_j ≥ 0; Σ phi_j = 1
ACS_final = min(ACS_raw, limites aplicáveis)
```

As definições abaixo são propostas operacionais para o piloto, e não medições já validadas:

| Dimensão | Observação possível na execução | Limitação |
|---|---|---|
| D | Preservação de spans/qualificadores e auditoria de alegações materiais | Recall real exige referência humana; passar validação de schema não prova completude |
| R_retrieval | Intenções executadas, cobertura de fontes primárias e rastreabilidade | Não chamar esta razão de Recall@k sem conjunto de referência |
| E | Cobertura material, massa efetiva, independência e busca contraditória | Combinação exige rubrica congelada e validação; não usar ESS como entrada |
| C | Compatibilidade temporal, geográfica, populacional e de denominador | Contexto desconhecido deve continuar desconhecido |
| Rob | Sensibilidade ao remover grupos e perturbar atributos dentro de faixas predefinidas | Teste numérico não demonstra robustez semântica a reformulações |

Antes de publicar ACS numérico, escrever manual de anotação para cada dimensão, definir a transformação para [0,1] e comparar proxies com auditoria humana cega. Não pedir ao modelo apenas “informe sua confiança”. Todas as dimensões obrigatórias precisam estar observadas; ausência implica `acs=null` com motivo. Não renormalizar pesos para esconder uma dimensão obrigatória ausente.

Se uma dimensão com peso positivo é exatamente zero, ACS é zero; calcular positivos no domínio logarítmico e tratar zero explicitamente. Não transformar zero em resultado positivo por um piso numérico. Limites para proveniência fraca, contexto parcial ou recuperação incompleta são versionados e precisam de calibração.

### 7.4 Parâmetros e decisão

Não existe um conjunto de pesos e limiares validado nos anexos. Criar `parameters.v1.candidate.json` com expoentes iguais como baseline exploratório, `γ=1` e parâmetros positivos explicitados. Valores `rho=0,20` e `lambda_M=2` reproduzem exemplos didáticos, mas não devem ser promovidos automaticamente a configuração científica de produção. `M_min`, caps e limiares de decisão ficam pendentes do piloto; sem configuração aprovada para o domínio, permitir modo experimental com aviso e impedir afirmação de calibração.

Ordem de decisão:

1. Não verificável → `NOT_VERIFIABLE`.
2. Falha crítica ou política de risco que exige intervenção → `HUMAN_REVIEW_REQUIRED` (indicar se há revisão disponível; não prometer fila inexistente).
3. Insuficiência/contexto impeditivo → `INCONCLUSIVE`, ESS indisponível.
4. ACS indisponível ou abaixo do limiar → abstenção, com a razão.
5. Massas opostas materiais, origens independentes e conflito acima do limiar → `CONTESTED`.
6. Direção do ESS → `STRONGLY_SUPPORTED`, `PREDOMINANTLY_SUPPORTED`, `PREDOMINANTLY_CONTRADICTED` ou `STRONGLY_CONTRADICTED`, conforme limiares congelados; zona sem decisão direcional → `INCONCLUSIVE`.

Se insuficiência e conflito coexistirem, estado principal inconclusivo e sinal secundário de conflito. Não mapear controvérsia e ausência de informação para o mesmo ESS=50. Alto ACS com ESS baixo é coerente: o procedimento pode ser adequado e a alegação contraditada.

## 8. Múltiplas alegações

Guardar métricas por claim e distinguir do resumo da entrada. Para claims válidos e comparáveis, `ω_i=Imp_i/ΣImp`, `ESS_X=50×(1+Σω_i(ESS_i-50)/50)`. Não excluir claim inválido e renormalizar silenciosamente: uma alegação material sem avaliação bloqueia o ESS global nesta versão conservadora.

Se uma alegação central for contraditada, o resumo deve declará-lo mesmo com periféricas sustentadas. Para claims logicamente dependentes ou de naturezas heterogêneas, não publicar média global; mostrar avaliações individuais. Criticidade é fixada antes dos resultados.

Proposta conservadora de ACS global para investigação: `min(ACS_i das claims materiais, 100×D_global, 100×cobertura_material)`, somente com todos os componentes disponíveis. É uma extensão de engenharia, não fórmula validada do memorial; comparar com alternativas no desenvolvimento. Até a validação, preferir ACS por alegação e indisponibilidade global a um número com interpretação ambígua.

## 9. Streaming, Markdown e apresentação

Reutilizar SSE via POST e autenticação Firebase. Enviar estágios de extração, pesquisa e avaliação enquanto o motor trabalha. Só iniciar a explicação factual depois de validar as evidências e congelar a decisão. Assim o texto incremental não anuncia uma conclusão posteriormente contradita pelo cálculo.

O redator recebe alegações, trechos aprovados, fontes autorizadas, decisão e limitações; recebe instruções curtas para explicar, sem escolher métricas. Limitar URLs às fontes recuperadas e validar referências. Mesmo assim, erro semântico na redação permanece possível: em casos de risco elevado, usar explicação por template ou validar o texto completo antes de liberá-lo, com custo de latência explicitado.

Contrato novo preserva `stage`, `delta`, `verdict`, `done` e `error`. Exemplo ilustrativo de metadados, sem interpretação probabilística:

```json
{
  "type": "verdict",
  "veredito": {
    "version": 2,
    "code": "INCONCLUSIVE",
    "analysis_id": "server-generated-id",
    "method_version": "core-v2-candidate",
    "calibrated": false,
    "scope": "claim",
    "metrics": [
      {"id": "ESS", "label": "Sustentação das evidências", "value": null,
       "min": 0, "max": 100, "valid": false, "reason": "INSUFFICIENT_EVIDENCE"},
      {"id": "ACS", "label": "Qualidade da análise", "value": null,
       "min": 0, "max": 100, "valid": false, "reason": "ROBUSTNESS_NOT_MEASURED"}
    ]
  }
}
```

Métricas ficam em um rodapé separado do corpo Markdown. ESS: barra direcional com centro 50 e legendas “contradiz”/“sustenta”; ACS: barra de qualidade do processo. Exibir número como `68/100`, rótulo textual e ajuda curta: “Índices experimentais; não são probabilidades”. Usar cor acompanhada de texto, contraste adequado e `meter` ou semântica acessível equivalente. Em `null`, mostrar “Indisponível — evidências insuficientes” e não desenhar preenchimento que pareça zero.

Mostrar detalhes de claims, fontes e limitações em expansão opcional. Não transmitir raciocínio interno. Barras só aparecem com resultado definitivo da análise, nunca aumentam junto com os tokens. Em erro/cancelamento, marcar resposta parcial e não mostrar score final como concluído.

Gerar `veredito` em código; não extraí-lo da explicação do modelo. Texto copiado pode receber um resumo das métricas gerado pelo servidor. Histórico novo usa o objeto salvo mesmo com `metrics=[]`; parser textual serve apenas para registros legados sem versão estruturada. Mensagens antigas exibem “não calculado nesta versão”, sem métricas retroativas.

O JSON e SSE passam pelo mesmo resultado de domínio, salvam os mesmos metadados e diferem apenas no transporte. Adaptar também `extensions/chrome/panel.js` e verificar seu contrato: a extensão não deve perder indicadores ou continuar apresentando apenas os quatro rótulos antigos.

## 10. Eficiência mensurável

As regras matemáticas, limites, decisões, templates e validações ficam em código/configuração; não precisam viajar no prompt. Prompts pequenos e especializados seguem contratos de dados. Qualificar vários trechos em lote reduz chamadas, desde que os IDs impeçam mistura de evidências entre claims.

Não enviar todo o histórico para todas as etapas: a extração recebe apenas contexto necessário à referência; qualificação recebe claim e trechos; redação recebe o dossiê aprovado. Respostas anteriores são contexto não confiável e não evidência.

Cachear recuperação e qualificação por claim normalizada, contexto temporal/geográfico, hash do conteúdo e versões; prazo por volatilidade. Não remover qualificadores para formar a chave. Cache de conteúdo privado deve ser segregado por UID/organização e apagável; cache público só recebe documentos públicos. Nenhum cache ignora autenticação, quota ou atualização de fatos.

```text
C_total = C_extração + C_busca + C_qualificação + C_redação + C_escalonamento
```

Registrar tokens de entrada, saída, raciocínio/cache quando expostos, buscas, latência e custo monetário por etapa. Mais chamadas podem custar mais que o fluxo atual: a economia é hipótese a testar por estrato e sob orçamento equivalente. O caminho de ruído é a única economia de tokens garantida por construção, pois não chama modelo.

## 11. Segurança e falhas

| Risco | Controle a implementar/preservar |
|---|---|
| Injeção no prompt, histórico, documento ou fonte | Tratar como dados sem autoridade; schemas fechados; parâmetros e decisões internos; isolamento de ferramentas; redator sem ações privilegiadas |
| Fonte maliciosa pede acesso a segredos | Nenhum segredo ou variável de ambiente disponível ao fluxo de conteúdo; ferramentas de rede só com operações e destinos permitidos |
| SSRF por links | Serviço de fetch isolado; permitir HTTP(S) público; bloquear endereços internos/reservados IPv4/IPv6 e metadata, credenciais em URL e portas não permitidas; validar DNS, destino conectado e cada redirecionamento; controlar egress contra rebinding |
| Downloads abusivos | Timeout, limite de bytes antes/depois da descompressão, redirects e concorrência; parsers isolados; MVP textual sem execução de arquivos |
| XSS/links hostis | Preservar Markdown sem HTML bruto; métricas via `textContent`; validar links finais; não usar HTML retornado diretamente por modelo ou fonte |
| Manipular ESS/ACS pelo payload | API não aceita scores, pesos, grupos, versão de política ou URLs autorizadas como autoridade do cliente |
| Acesso a outra conversa/análise | UID derivado do token em todas as consultas, também snapshots, auditoria e cache privado; testes de autorização por objeto |
| Esgotamento de saldo/workers | Rate limit inclusive rejeições, quota e reserva atômicas, orçamento por análise/usuário/global, deadline e concorrência limitada |
| Fraude por múltiplas cópias | Deduplicação e proveniência por unidade; incerteza de origem limita suficiência/ACS |
| Resposta parcial ou desconexão | Cancelar tarefas pendentes; registrar gasto real; liberar lease uma vez; impedir metadados finais incompletos |
| Falha ao persistir | Não enviar `done`; resultado auditável persistido antes da confirmação; chave idempotente por UID e requisição |
| Vazamento na auditoria | Logs operacionais sem texto sensível/segredos; snapshots com acesso restrito, retenção definida e exclusão vinculada ao titular |

Reservas precisam distinguir sucesso, falha sem gasto e falha com gasto. O fluxo atual reembolsa a quota quando falha, mas pode já ter consumido tokens: no desenho novo, registrar custo ao longo das etapas, inclusive execução incompleta, sem permitir retries ilimitados gratuitos. Retentativas usam chave idempotente, não uma segunda reserva invisível.

Separar a trilha de aplicação das permissões de administração. Auditoria com permissões apenas de acréscimo e verificação de integridade aumenta rastreabilidade, mas um hash isolado não torna o banco inviolável. Nenhuma arquitetura garante impedir todo usuário malicioso: validar controles com testes adversariais e limites operacionais.

## 12. Plano de integração por arquivo

| Arquivo/módulo | Mudança proposta |
|---|---|
| `src/core/contracts.py` | Contratos, estados oficiais, validação estrita e distinção null/zero/NA |
| `src/core/input_gate.py` | Rejeição local conservadora e resultado curto por template |
| `src/core/scoring.py` | Pesos, dependência, ESS, conflito, ACS e diagnóstico de validade, sem rede/LLM |
| `src/core/decision.py` | Gates, política de risco e agregação multiclaim |
| `src/core/parameters/` | Parâmetros candidatos versionados, sem edição pelo cliente |
| `src/services/analysis_service.py` | Orquestração, orçamento, cancelamento e resultado único para JSON/SSE |
| `src/services/retrieval_service.py` | Adaptador de busca, snapshots, acesso controlado e proveniência |
| `src/services/openai_services.py` | Adaptadores semânticos e redação; remover autoridade sobre score/veredito |
| `src/services/chat_events.py` | Contrato V2 estruturado; parser textual apenas legado |
| `src/controller/chatController.py` | Gate barato após controle de tráfego; resultado unificado; persistência JSON/SSE simétrica |
| `src/models/chatModel.py` | Referência da análise e metadados em ambos os transportes |
| `src/models/analysisModel.py` | Snapshots, features, decisões e auditoria segregados |
| `src/models/userModel.py` | Separar tráfego, análises e custo; idempotência e finalização por etapa |
| `static/js/chat.js`, `static/css/chat.css` | Rodapé acessível de métricas e estados; preservar corpo/renderizador |
| `extensions/chrome/panel.js` | Mesmo contrato e interpretação de estados/métricas |

Implementar em etapas: contratos/motor puro → triagem e orçamento → recuperação/qualificação auditáveis → integração de transporte e UI → piloto/calibração. Até completar recuperação e atributos, manter scores indisponíveis; não fabricar métricas para demonstrar a interface. Não chamar a fase de projeto de algoritmo já implementado.

## 13. Testes e critérios para a banca

Testes numéricos: reproduzir os exemplos do memorial; limites e finitude; ESS monotônico com suporte independente; troca de sinal espelha `100-ESS`; dimensão ACS zero zera produto; ausência obrigatória dá null; nenhuma evidência dá null; cópias idênticas não aumentam contribuição; conflito com pouca massa não vira controvérsia automaticamente.

Testes de integração: ruído não chama provedor; siglas/perguntas curtas não são bloqueadas indevidamente; referência usa só histórico autorizado; quatro intenções registradas; URL/trecho inventado rejeitado; origem desconhecida não vira independência; claim crítica omitida bloqueia resumo; JSON e SSE persistem objeto idêntico; recarregar preserva métricas; Markdown mantém tabelas/negrito e fragmentação UTF-8; extensão renderiza o mesmo resultado; cancelamento não duplica quota/custo.

Testes adversariais: injeção em cada superfície, scores enviados pelo cliente, documentos repetidos, troca de tempo/população, DNS/redirect para rede privada, payloads oversized, falhas de busca/banco, acesso cruzado entre UIDs e cache contaminado. Cobrir também quando o redator tenta contradizer a decisão congelada.

Protocolo experimental conforme memorial §§45–56:

- Piloto de 100–200 casos para ajustar rubricas e estimar necessidades amostrais; não prometer precisão com esse tamanho.
- Anotação independente e adjudicação; avaliadores cegos aos scores e ao sistema avaliado.
- Desenvolvimento/calibração/teste inicialmente 60/20/20, agrupados por evento, família de fontes e pares metamórficos para evitar vazamento.
- Comparar LLM direto, LLM com busca, RAG simples e Core sob orçamento equivalente, registrando custo e latência.
- Medir Material Claim Recall, stance/citação, Macro F1, erros críticos, cobertura, risco seletivo e AURC, além de custo/latência e falsos bloqueios da triagem.
- Intervalos agrupados por evento; parâmetros congelados antes do teste; avaliação temporal posterior.
- Brier/ECE somente para alvo probabilístico definido e calibrado, nunca tratando ESS como probabilidade por conveniência.

Só afirmar “mais eficiente” ou “melhor que IA padrão” após ganho observado com incerteza reportada. Se não houver ganho de acerto, avaliar se rastreabilidade/abstenção justificam o custo; simplificar se necessário. Para o artigo, distinguir claramente implementação atual, algoritmo projetado, resultados do piloto e validação ainda pendente.

## 14. Resultado esperado

Entradas inequívocas sem sentido recebem resposta local curta sem tokens de IA. Entradas factuais seguem um processo limitado e auditável. O cálculo fica fora do prompt, e o rodapé recebe índices estruturados sem interferir no Markdown. O sistema pode concluir sustentação, contradição ou controvérsia, e pode reconhecer que não há condições de atribuir um número responsável.
