# Aleteia Core — implementação e operação

## Modos de resposta: padrão e experimental

O modo **padrão** voltou ao fluxo de uma única geração, com o `SYSTEM_PROMPT` anterior a ESS/ACS, recuperado do commit `5c7ba6a`. `src/services/standard_service.py` envia prompt/histórico limitado ao modelo, com busca web nativa opcional como na implementação antiga, e transmite a resposta incrementalmente. Não executa extração, qualificação, leitura independente ou cálculo dos índices. Autenticação, limites de entrada/tráfego, contabilização de tokens e renderização segura continuam vigentes. O prompt antigo está separado em `src/services/standard_prompt.py`, sem importar ou inicializar o SDK Gemini.

Todo o algoritmo descrito nas seções seguintes pertence exclusivamente ao **modo experimental**. Na interface, o menu “Modelo” fica no rodapé da caixa de mensagem e começa em **Básico** (modo padrão). As opções **Básico** e **Experimental** descrevem suas diferenças, incluindo ausência/presença de ESS/ACS e o possível tempo adicional de análise. A opção experimental informa o risco antes da seleção; selecioná-la também exibe: “O algoritmo experimental está em fase de desenvolvimento e pode gerar erros e respostas inconsistentes.” O aviso permanece enquanto estiver ativa. A escolha vale para a próxima requisição, inclusive na extensão que incorpora o mesmo chat; recarregar a página começa novamente em Básico. O menu abre para cima, aceita navegação por teclado, fecha por Escape ou clique externo e fica desabilitado durante a geração.

`POST /api/chat/mensagem` aceita `mode: "standard" | "experimental"`; omitir o campo usa `standard`. Valores inválidos são rejeitados antes da reserva de uso/chamada ao provedor. A camada de serviço também usa padrão `standard`; mencionar o modo no texto do prompt não muda o roteamento. Não há falha automática do padrão para o experimental nem mistura dos índices entre modos.

Ambos os modos funcionam em JSON e SSE. O modo é salvo em `veredito.mode` com a própria resposta, sem migração destrutiva. Respostas padrão usam o veredito simples anterior, sem indicadores nem aviso de “métricas não calculadas”. Respostas experimentais mantêm indicadores, fontes e auditoria e recebem identificação própria. Mensagens históricas preservam suas avaliações; abrir o histórico não reexecuta nenhum algoritmo. O modo padrão não grava snapshots de pesquisa experimental.

## Decisão contextual e fontes principais — V5

Método atual `core-v5.0-candidate`, parâmetros `contextual-decision-2026-11-v9`. A lógica distingue compatibilidade com a proposição, inferência indireta, outro contexto, mera menção e relação incerta. Essa classificação é geral: pessoa, tempo, população, modalidade, hipótese/ocorrência, ficção/realidade, proposta/fato vigente. Contextos diferentes e citações sem afirmação não viram votos; inferências indiretas recebem força parcial. Não é necessário que uma página repita literalmente a pergunta. A ausência de sustentação mantém a presunção revisável descrita abaixo; relatos reais conflitantes continuam distinguíveis de coincidências textuais.

A segunda leitura pode examinar janelas contíguas dos documentos omitidos pela primeira. Esses candidatos têm qualidade desconhecida e começam neutros; não recebem provas ou notas inventadas. A validação final usa a mesma base de cálculo da publicação, inclusive em anotações com atributos incompletos. Antes, um filtro anterior ao cálculo descartava essas anotações e podia produzir um falso bloqueio de alinhamento.

Há três formas identificadas de ESS além do cálculo integral: `observed_support` para ausência de sustentação observada; `provisional_direction` para direção semântica inspecionada com atributos incompletos; `undetermined_support` para ponto neutro 50 quando não há direção determinável. O valor neutro não significa 50% de chance de verdade. No estimador provisório, cada direção assinada é corrigida por tamanho do grupo de origem e por tipo de recuperação (sínteses ×0,25), com a mesma regularização rho, sem preencher SQ/R/CF ausentes. ACS fica limitado a 35 (25 se a qualificação/decomposição não foi concluída), multiplicado pela cobertura de pesquisa. Os proxies e limites são política experimental, não calibração estatística.

Uma pesquisa auditada com evidência insuficiente ainda gera resposta, estado e índices com limitações explícitas. Sem documentos, a qualificação é pulada e a leitura independente resume o resultado: ESS neutro e ACS zero, sem inventar fatos. Se a saída da primeira qualificação não pode ser validada, a leitura independente já prevista avalia snapshots sem notas prévias. Não se repetem as buscas. Falhas de execução/autenticação do provedor continuam erros operacionais, sem serem apresentadas como prova de falsidade.

As citações do corpo usam nomes/títulos reais e tamanho menor, com a mesma renderização segura durante o streaming e após a conclusão. “Principais fontes” substitui o inventário público: inclui provas decisivas, contrapontos materiais e contexto necessário, preservando as fontes citadas no corpo. Fontes incidentais/apenas localizadas saem dessa lista; o inventário completo permanece na auditoria privada. URLs são deduplicadas por destino, removendo fragmentos e parâmetros de rastreamento, preservando parâmetros que distinguem artigos. Um mesmo domínio pode ter documentos diferentes importantes. A seleção é limitada a quatro fontes por alegação (duas em conclusões só contextuais), doze no total, sem exigir preencher esses limites.

Markdown bruto continua sem HTML; links e rótulos são escapados/validados, e as citações abrem com `noopener noreferrer`. A lista também filtra duplicatas e fontes apenas localizadas em registros legados. Os testes incluem fontes de direções opostas, rastreamento duplicado, parâmetros de identificação distintos, omissões da primeira leitura, recuperação de qualificação e atributos incompletos, além dos cenários gerais de contexto. A integração com documentos reais do exemplo confirmou resposta e direção provisória com ESS/ACS calculados; não constitui uma garantia para todas as perguntas possíveis.

## Contexto declarado e presunção revisável — V4.2

Método `core-v4.2-candidate`, parâmetros `context-safe-search-2026-11-v8`. A reprodução real de “o alanzoka foi preso?” revelou que a extração havia inventado um nome civil no contexto. A avaliação subsequente tratou fontes sobre o apelido como pessoas diferentes e bloqueou ESS/ACS por identidade incerta. A regra V4.1 isolada não resolvia esse erro.

O intake agora substitui contexto gerado por trechos literais da entrada e do histórico do próprio usuário. Identificações e datas novas devem vir dos documentos; não ganham autoridade por terem sido completadas pelo extrator. A segunda leitura recebe mais contexto contíguo em torno das citações para conferir vínculos entre apelido e nome civil, sem receber os sinais ou a resposta da primeira leitura.

Quando a pesquisa validada resulta em `NO_SUPPORT_FOUND`, Python publica texto consistente com o veredito: presume provisoriamente a não ocorrência, explicita a ausência de confirmação nas fontes consultadas e admite revisão diante de um registro confiável. Essa regra não converte ausência de resultados em prova universal de falsidade, nem converte falhas de pesquisa em não ocorrência. Os limites e as condições da V4.1 abaixo continuam vigentes.

A validação completa na API, após a correção, executou duas buscas e cinco chamadas totais, consumiu 32.874 tokens observados e retornou `NO_SUPPORT_FOUND`, ESS=0 (sustentação encontrada) e ACS=75. Isso verifica integração desse caso real, não garante precisão universal nem estabelece um histórico criminal completo. Os testes de regressão incluem contexto de identidade inventado, nome declarado pelo usuário e referência legítima ao histórico.

## Pesquisa sem sustentação — V4.1 (16/11/2026)

Método `core-v4.1-candidate`, parâmetros `search-support-2026-11-v7`. Ausência de confirmação pode produzir uma resposta útil e o estado `NO_SUPPORT_FOUND` (“Sem sustentação nas fontes consultadas”), distinto de contradição factual e de relatos inconclusivos. O leitor independente recebe também registros de execução da pesquisa, sem a resposta/direções do primeiro leitor. Identifica ausência de suporte, relatos confusos e identidade resolvida. Contexto neutro, como atividade pública recente, deve ser retido, mas não passa a ser prova de que um evento jamais ocorreu.

O caminho exige alvo factual positivo de ocorrência, identidade resolvida, revisão fiel, quatro objetivos efetivamente pesquisados, nenhum job falho, ao menos um trecho contextual ancorado, ausência de qualquer anotação direcional e auditoria `no_support_found`. Não se aplica a causalidade, orientação pessoal, afirmações negadas ou fatos privados/inacessíveis. Relatos positivos, mesmo com atributos desconhecidos, impedem essa conclusão automática; pesquisa falha ou identidade ambígua não é ausência de confirmação.

Nesse estado, ESS recebe `measurement=observed_support`: 0% significa **zero sustentação encontrada no conjunto consultado**, não 0% de chance de verdade, prova de falsidade ou ESS direcional calculado com massa negativa. Não se inventa contraprova. O círculo identifica explicitamente esse significado. ACS mede o procedimento por D (revisão fiel), R (objetivos executados), T (rastreabilidade do contexto, 1 para documento inspecionado ou 0,5 para síntese citada) e C (compatibilidade contextual), usando média geométrica e tetos de 75/60 respectivamente. Esse proxy não mede a completude da internet nem probabilidade de nunca ter ocorrido.

Não há novas chamadas ao modelo ou novas rodadas de pesquisa. Markdown, streaming e gavetas permanecem. Testes simulados incluem a pergunta do streamer, pesquisa com apenas sínteses, identidade ambígua, busca falha e menções confusas; não constituem uma checagem factual real da pessoa mencionada.

## Política atual: alvo preservado e pesquisa econômica — V4 (16/11/2026)

Método `core-v4.0-candidate`, parâmetros `anchored-economical-2026-11-v6`, política `anchored-economical-v2`. Esta seção substitui as políticas históricas abaixo. A produção usa `src/core/answer_policy.py`; o motor estrito permanece como diagnóstico de auditoria.

**ESS mede o apoio à afirmação enviada, não à resposta corrigida.** Perguntas fechadas e afirmações declarativas congelam `original_span` como alvo antes da pesquisa, preservando negação, ano, população e erros de digitação. Entidades do histórico podem ser esclarecidas no contexto. Uma conclusão corretiva nunca substitui esse alvo. Apenas perguntas abertas podem ser resolvidas em uma nova proposição explicitamente apresentada. Escopos explicativos continuam separados e não viram votos favoráveis à hipótese original.

A primeira leitura qualifica fontes e ancora citações literais. Uma segunda leitura compacta, sem acesso à resposta ou aos sinais da primeira, avalia esses trechos contra o alvo preservado. Retorna categorias de apoio/contradição direta/parcial/neutra e uma resposta curta; Python converte essas categorias na rubrica assinada. IDs, alvo, citações e coerência entre conclusão e massa final são validados antes da pontuação. Não se invertem índices por palavras como “não”. Essa leitura independente reduz uma falha observada, mas não constitui prova de correção semântica universal.

**Pesquisa:** uma alegação usa duas chamadas de busca: fonte primária com contexto neutro, e suporte com procura ativa de contraprova. Os quatro objetivos são documentados; as contagens mostram duas chamadas reais, sem apresentar objetivos como quatro consultas executadas. Até quatro chamadas de busca por análise, compartilhadas entre alegações, sem expansão automática por risco, controvérsia ou escassez. Objetivos não pesquisados continuam registrados como pendentes. A seleção prioriza páginas textuais, diversidade e poucos documentos pertinentes: até oito materiais e 20.000 caracteres para qualificação. Links apenas localizados ficam identificados como tal na gaveta de fontes.

O fluxo usual de uma alegação tem cinco chamadas ao modelo: extração, duas buscas, qualificação e conferência semântica. Uma reparação de escopo pode acrescentar uma chamada. Há teto global de oito chamadas ao modelo, quatro buscas, deadline de 180 segundos, até 6.000 tokens de saída na qualificação e 3.000 nas outras etapas estruturadas. Busca para de iniciar chamadas após 45.000 tokens observados; as etapas restantes têm interrupção em 80.000 observados. Essa reserva comporta os contextos de quatro buscas em voo em entradas com várias alegações, sem acrescentar consultas. Chamadas em voo e contexto interno do provedor podem exceder esses valores: não são teto monetário absoluto. O limite de buscas reduz o principal custo observado sem eliminar o orçamento da avaliação final.

**ACS:** combina verificação estrutural/semântica, cobertura dos objetivos de pesquisa realmente executados, qualidade/suficiência das evidências, compatibilidade contextual e sensibilidade dos atributos. A perturbação de SQ/R/CF em ±0,05 mede estabilidade numérica; remover a única fonte e obter um conjunto vazio fica como diagnóstico separado, não como falha automática do procedimento. Qualidade e contexto ponderam grupos de origem para que cópias não alterem a nota. Um documento diretamente inspecionado, competente e pertinente pode bastar. Não há quantidade mínima artificial de sites.

Prova direta suficiente determina a base dos índices; sínteses derivadas não a diluem nem a multiplicam. A suficiência procedural usa a capacidade evidencial do material inspecionado, separada da força direcional da conclusão: uma conclusão cautelosa bem documentada pode ter ACS alto e ESS baixo. Um contraponto presente somente em síntese não verificada permanece sinalizado e limita o ACS. Quando sínteses são essenciais, mantêm desconto de massa e limite de qualidade; atributos desconhecidos não recebem valores inventados. Evidência conflitante, fraca ou contextualizada continua refletida na avaliação.

Em alvos causais, a classificação independente distingue resultado causal, mera associação e causalidade não estabelecida. Python impede que `association_only` conte como apoio causal. Incerteza causal e sínteses secundárias recebem no máximo força parcial, sem marcadores de contraprova direta; um resultado causal direto exige origem primária ancorada. Isso evita confundir estudos de associação divergentes com provas causais opostas. Não demonstrar causalidade pode contrariar uma afirmação categórica sem demonstrar impossibilidade absoluta.

O objetivo continua responder com o material disponível e publicar índices quando há evidência qualificável. Um ESS baixo pode coexistir com ACS alto: pouco apoio à hipótese, boa qualidade do procedimento. ACS reduzido não apaga automaticamente uma conclusão fundamentada. Sem material qualificável, não se fabrica percentual. Decisões individuais de tratamento mantêm o cuidado específico; perguntas científicas gerais não recebem revisão humana automática.

Os círculos, Markdown, streaming e duas gavetas recolhidas são preservados. ESS/ACS são índices normalizados apresentados em %, **não probabilidades empiricamente calibradas de verdade/acerto**. As verificações de regressão e integração descritas aqui não demonstram superioridade estatística frente a outras IAs.

Na integração real da pergunta “paracetamol causa autismo no bebê se a mão ingerir durante a gestação?”, a pesquisa agrupada executou duas chamadas de busca e cinco chamadas totais ao modelo, usando aproximadamente 37,5 mil tokens observados e cinco materiais, em vez de expandir para dezenas de consultas. Ao reavaliar esses mesmos snapshots com as regras finais de inferência, o alvo original recebeu ESS≈15,3 e ACS=85, `PREDOMINANTLY_CONTRADICTED`, sem rejeitar a resposta por falta de mais fontes. O erro “mão” foi esclarecido no contexto, sem alterar a hipótese. O resultado testa coerência e integração desse caso; os valores podem variar com os documentos encontrados e não representam acurácia validada.

## Registro histórico: resposta primeiro — V3 (substituída)

Método `core-v3.0-candidate`, parâmetros `answer-first-2026-11-v5`, política `answer-first-v1`. Esta seção substitui as restrições de publicação V2 descritas no registro histórico abaixo. O motor estrito permanece apenas em `strict_diagnostic`; a produção chama `src/core/answer_policy.py`.

O objetivo é responder com a evidência qualificada disponível e comunicar limitações nos índices e no texto. Lacunas parciais, ausência de texto integral e ACS abaixo do limiar antigo não apagam automaticamente ESS/ACS nem impedem a resposta. Com evidências relevantes, atributos conhecidos e massa direcional positiva, publica-se ESS regularizado. Sínteses citadas têm contribuição reduzida a 25% e identificação explícita; cópias continuam agrupadas, sem votação por popularidade. Informação irrelevante, conteúdo inventado, ruído e ausência de qualquer material qualificado continuam sem percentual factual fabricado.

Os indicadores aparecem em **% de sustentação e de qualidade**, não como probabilidades estatisticamente calibradas de verdade/acerto. O método não foi calibrado empiricamente e não permite prometer “98% de chance de verdade”. ESS continua direcional: baixo pode indicar forte evidência contrária. ACS combina verificações realizadas de estrutura/semântica, recuperação, suficiência/cobertura, contexto e sensibilidade. Metade de D corresponde à verificação estrutural e metade à revisão semântica; uma revisão não realizada não ganha crédito. O uso essencial de sínteses limita o ACS, mas sínteses complementares não penalizam prova documental suficiente. Avaliação com incerteza não é automaticamente ausência de resposta.

`personal_advice` distingue decisão clínica individual de pergunta científica geral. Um assunto de saúde pode exigir mais pesquisa sem exigir encaminhamento humano. Orientação individual de tratamento/dose/interrupção mantém sinalização específica, sem apagar índices que foram medidos. `analysis_overreach` avalia excesso na própria resposta; uma hipótese causal não comprovada não invalida um procedimento que conclui corretamente “causalidade não estabelecida”. Formulação que extrapola a evidência tem confiança reduzida e não é publicada como síntese categórica.

Pesquisa adaptativa: fatos simples consolidados usam uma rodada de quatro intenções; temas controversos, causais ou de maior risco usam três rodadas (12 consultas por claim); temas obscuros usam quatro (16). Escassez de resultados na primeira rodada também amplia a busca. Há teto compartilhado de 32 consultas por análise, até 32 documentos/sínteses, 60.000 caracteres para qualificação e 32 evidências anotadas. Isso amplia cobertura; não transforma quantidade de links em certeza. As contagens mostram o que foi efetivamente executado.

Limites operacionais atuais: 36 chamadas por análise, deadline de 240 segundos, timeout de até 50 segundos por chamada, até 12.000 tokens de saída na qualificação. A busca deixa de iniciar chamadas após 190.000 tokens observados, reservando orçamento para concluir a análise até 250.000 tokens observados. São limites de interrupção, não teto monetário absoluto para chamadas em voo. O lease por usuário é de 360 segundos. Mais pesquisa custa mais; configure orçamento no provedor e timeout compatível na infraestrutura. Não houve alteração de credenciais ou de quota diária de perguntas.

O rodapé mantém duas gavetas independentes: **Análise das fontes** (trechos qualificados, stance e justificativa) e **Todas as fontes** (links completos com status: avaliada, consultada, síntese ou apenas localizada). “Localizada” não é apresentada como texto integral lido. As gavetas começam recolhidas; os círculos, Markdown e streaming são preservados.

Na verificação médica com material real sobre paracetamol/autismo, o fluxo completo executou 12 consultas, localizou 53 fontes, avaliou 16 materiais e publicou ESS≈20,6% e ACS≈62,9%, classificando a alegação causal como predominantemente contraditada e oferecendo síntese contextual, sem bloqueio humano genérico. Não se conclui “impossibilidade causal provada”: a [OMS](https://www.who.int/news/item/24-09-2025-who-statement-on-autism-related-issues) informa que não há evidência conclusiva ou associação consistente estabelecida para exposição na gravidez. Esse comunicado também aborda vacinas; não se deve atribuir ao paracetamol a passagem sobre estudos de vacinas desacreditados. A [meta-análise citada](https://pubmed.ncbi.nlm.nih.gov/41062061/) distingue associação observacional, confundimento e diagnósticos. Esse teste verifica integração, não validação estatística do algoritmo.

## Registro histórico das políticas V2

## Suficiência direcional e preservação do alvo — versão 2.4

Método `core-v2.4-candidate`, parâmetros `directional-sufficiency-2026-11-v4`, prompt `directional-proof-v4`.

A cobertura de elementos não tem a mesma interpretação para confirmação e refutação. Para sustentar integralmente uma alegação, continuam necessárias as condições materiais pertinentes. Para refutar uma alegação conjuntiva, uma condição necessária diretamente contraditada pode bastar. A ausência de evidência e o silêncio de fontes nunca são considerados refutação.

O qualificador registra `refutation_kind=explicit_contradiction` e `refutes_elements`. O servidor valida IDs, trecho literal, índices e sua inclusão nos elementos examinados. O motor só aceita a contraprova como suficiente se vier de documento diretamente inspecionado, stance=-1, SQ≥0,75, R=1, CF=1, massa suficiente e contexto coincidente. A cobertura material bruta é preservada; `decision_coverage=1` descreve suficiência para essa refutação, sem alegar que foram verificados os detalhes restantes. Não se aplica o teto de incompletude a uma contraprova suficiente. O contexto relevante é o da condição refutada, não o de explicações históricas dispensáveis. Causalidade indevida e risco continuam sujeitos aos gates próprios.

Perguntas sim/não recebem `verification_target`. A proposição original permanece na avaliação mesmo quando a pesquisa encontra fatos corretivos ou contextos históricos. Evidências de 2018 não se tornam provas contrárias a 2026 só por serem de outro ano. Uma informação oficial diferente para o mesmo atributo em 2026, porém, pode contradizer diretamente o tema atribuído a 2026. O veredito global toma os alvos enviados para verificação; fatos explicativos não viram votos favoráveis que diluam a atribuição falsa.

`relation_type` separa categoria/atribuição/estatística de causalidade. Verificar se “manipulação de comportamento” era o título de um tema não é afirmar que a prova manipulou pessoas. `causal_overreach` só bloqueia o tipo causal. Isso evita tratar palavras de títulos, falas ou temas como hipóteses causais adicionais inventadas.

Resumos multiclaim com partes sustentadas e partes contraditadas podem ser `MIXED` (apresentação agregada), em vez de receber automaticamente “inconclusivo”. Alegações centrais falsas mantêm sua precedência; os oito estados por alegação permanecem, sem média global que esconda uma falsidade central. Os contextos e métricas individuais continuam visíveis.

Reutilizando as evidências reais da pergunta sobre atribuir a 2026 o tema de manipulação de dados, o alvo original foi classificado como `STRONGLY_CONTRADICTED`, ESS≈5,0 e ACS≈98,3. O contexto de 2018 permanece explicativo. Trata-se de teste de integração e coerência lógica, não de prova de calibração ou garantia de precisão geral. Não foram elevados pesos ou limiares para forçar um número alto; corrigiram-se a unidade avaliada, o tipo de alegação e a suficiência da contraprova.

## Revisão de escopo e interface — 15/11/2026

Método atual: `core-v2.4-candidate`; parâmetros: `directional-sufficiency-2026-11-v4`; prompt: `context-scopes-footer-v3`.

Perguntas que envolvem edições, datas ou populações diferentes são delimitadas em `resolved_scopes`. Cada unidade tem sua própria proposição, elementos materiais, evidências e revisão contextual. A fonte de um ano não precisa provar outro ano e não é tratada como contradição do outro. Os escopos preservam o risco, a criticidade e a origem na pergunta do usuário. O frontend mostra círculos ESS/ACS por proposição, sem calcular uma média enganosa entre respostas condicionais.

Documentos recuperados são candidatos: trechos neutros, sem relevância ou de contexto incompatível não contaminam a suficiência de evidência válida. São preservados na auditoria; não passam a valer como prova. Uma síntese complementar do provedor não limita o ACS quando já existe evidência direta suficiente. A ausência de comprovação de uma cadeia editorial completa não é confundida com ausência de um documento diretamente inspecionado.

Uma única fonte pode ser suficiente para uma proposição delimitada. É necessário haver cobertura material completa, massa mínima, atributos conhecidos e pelo menos um documento diretamente inspecionado com SQ≥0,75, R=1 e CF=1. Essa exceção remove o teto automático por número de grupos. Se a origem primária desse documento não foi comprovada, conserva-se o aviso e o ACS fica limitado a 75, em vez de 35. Evidência fraca, sínteses essenciais e lacunas materiais mantêm os gates e caps conservadores. Os scores continuam calculados pela fórmula; não são elevados para um valor fixo nem pelo número bruto de links. Essas são políticas candidatas, não calibração estatística.

Quando o qualificador descreve novos escopos, mas devolve anotações com o ID da pergunta-pai, faz-se no máximo uma qualificação adicional com IDs explícitos. Não se copiam automaticamente as avaliações do pai para anos distintos. O teto de chamadas passa a 19; orçamento observado de tokens, concorrência e deadline continuam vigentes.

O corpo Markdown contém a resposta e citações breves. Contagens da pesquisa e avaliações individuais saem do corpo e ficam no rodapé estruturado, junto dos círculos. “Análise das fontes” usa `details/summary` nativo, recolhido por padrão e acessível por teclado. Trechos e justificativas usam texto seguro; os links são validados. Os círculos usam preenchimento proporcional e cores, acompanhados de rótulos: ESS baixo significa evidência contrária, não baixa qualidade. O ACS representa o procedimento. Ausência e limite superior mantêm apresentações distintas de um score exato.

Na verificação com documentos reais do Enem, os escopos 2019 e 2026 produziram respectivamente ESS≈91,0 / ACS≈71,0 e ESS≈95,3 / ACS≈98,2. Isso demonstra integração e elimina o falso bloqueio por escopo composto nesse caso; não demonstra precisão geral ou calibração.

## O que está aplicado

O chat usa o pipeline em `src/services/analysis_service.py`, com cálculo puro em `src/core/scoring.py`. O prompt de sistema anterior foi substituído por extração e qualificação com contratos estruturados e rubricas limitadas. A explicação combina uma síntese fundamentada produzida na própria qualificação com trechos, citações clicáveis e a decisão calculada em Python. Não há chamada extra de redação nem números escolhidos livremente pelo modelo.

O código mantém a Responses API e o modelo definido por `OPENAI_MODEL` (padrão `gpt-5-mini`). São necessárias as permissões de busca web e saída estruturada nesse modelo/projeto. O backend só utiliza URLs expostas nos eventos de busca do provedor, e busca seus documentos com um cliente de rede restrito. A presença de links no texto do modelo não comprova busca.

O adaptador segue os contratos oficiais de [eventos e fontes da busca web](https://developers.openai.com/api/docs/guides/tools-web-search) e [saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses). A biblioteca OpenAI continua fixada em `requirements.txt`; a conversão de schema usa o helper dessa versão.

Uma alegação factual usa até seis chamadas: extração, quatro recuperações com intenções distintas e qualificação em lote. Várias alegações compartilham extração/qualificação, mas cada alegação verificável recebe quatro recuperações. Com quatro alegações, o caminho normal tem até dezoito chamadas e dezesseis buscas; uma reparação de escopo pode levar a dezenove chamadas. A separação das intenções permite verificar a execução de cada uma e executar consultas em paralelo; há custo adicional frente ao chat simples. Não foi demonstrada economia em entradas factuais.

Entradas inequivocamente sem sentido usam zero chamadas de IA e resposta local curta. Perguntas curtas, siglas, fórmulas, idiomas diversos e referências ao histórico não são rejeitadas só por tamanho ou entropia. Entradas semanticamente fora de escopo ou sem assunto identificável e sem antecedente passam apenas pela extração, sem pesquisa posterior.

Desde `core-v2.2-candidate` / prompt `research-first-v2`, falta de contexto recuperável não interrompe o fluxo. `src/core/research_intake.py` cria uma tarefa de investigação quando o extrator pede contexto apesar de existir um tema pesquisável. A tarefa usa as mesmas quatro buscas e a qualificação existentes, sem chamada extra de classificação. Referências como “isso é verdade?” podem usar o assunto da mensagem anterior do próprio usuário; sem assunto ou antecedente, pede-se somente o assunto. Saudações, ruído e solicitações fora de escopo mantêm seu tratamento econômico.

Perguntas são preservadas como questões de investigação mesmo se o modelo as reescrever como afirmação. Datas, locais e entidades ausentes não são inventados. Em eventos periódicos, as consultas procuram a edição recente e a origem histórica relacionada. A qualificação explica interpretações e condições em linguagem direta. Uma pergunta aberta só pode receber ESS quando `resolved_claim` delimita uma proposição decidível e `resolution_source_ids` aponta para evidências que passaram pela validação de trechos; a proposição avaliada fica visível na resposta. Caso contrário, a IA ainda responde com o material encontrado, mantendo o ESS indisponível. Flags de risco e limites de entrada são preservados nessa recuperação.

## Métricas e decisão

ESS: média geométrica SQ/R/CF com expoentes iguais, contribuição assinada e correção por dependência com γ=1; regularização `rho=0,20`; massa mínima `0,60`. Conflito usa `lambda_M=2`. Esses valores são **parâmetros candidatos de engenharia**, não resultados experimentais. Método atual: `core-v2.4-candidate`; parâmetros: `directional-sufficiency-2026-11-v4` (15/11/2026).

ACS usa cinco dimensões com pesos iguais. D utiliza validação de spans e auditoria semântica do qualificador; R usa intenções de recuperação executadas; E usa massa/cobertura; C usa compatibilidade anotada; Rob mede sensibilidade numérica à remoção de grupos e perturbações de atributos. **Esses proxies não são recall humano nem robustez semântica validada.** Cada dimensão obrigatória desconhecida torna o ACS indisponível. Zero observado continua zero. Busca ou cobertura incompleta limita o ACS calculável a 50. Em material limitado, um único grupo limita ACS a 55; origem incerta, a 35; uso necessário de sínteses citadas do provedor, a 25. As exceções por prova documental suficiente estão descritas na revisão 2.3 acima. Esses limites são política candidata versionada, não probabilidades calibradas.

Para E, sínteses citadas podem contribuir com um quarto de sua massa anotada, exclusivamente como sinal limitado da qualidade do procedimento. Elas não entram em S+/S−, ESS ou conflito direcional. Uma falha observada na decomposição pode produzir D=0; a ausência de auditoria continua null. Compatibilidade parcial explicitamente avaliada recebe fator 0,5 em C; causalidade indevida observada recebe zero. Não se preenchem atributos desconhecidos com valores altos.

Se há evidência anotada, mas dimensões obrigatórias do ACS permanecem desconhecidas, o ponto ACS continua null. É possível exibir um **limite superior**, como “ACS ≤25/100”, calculado matematicamente colocando cada dimensão desconhecida no máximo permitido (1), preservando as observadas e aplicando os caps. O frontend identifica esse número como limite superior, não como medição exata nem probabilidade. Nenhuma evidência implica ausência também desse limite público. Isso comunica a baixa qualidade máxima possível do procedimento sem inventar atributos ausentes.

O limiar experimental de aceitação é ACS≥65; conflito ajustado≥0,45 exige massas opostas de grupos diferentes. ESS≥85 e ≥60 distingue sustentação forte/predominante; limites espelhados distinguem contradição. Verificabilidade, contexto, suficiência, criticidade e risco têm precedência. Casos de risco concreto exigem revisão humana, sem prometer serviço de revisão automático.

Atributos ausentes, omissão de elementos materiais, busca incompleta ou ausência de trechos de páginas diretamente inspecionadas bloqueiam ESS. Origem incerta é sinalizada, agrupada conservadoramente e reduz o ACS; não elimina automaticamente um documento secundário cujo trecho pôde ser inspecionado. Um trecho literal comprova presença textual, mas a relação lógica com a alegação ainda é uma anotação sujeita a erro. Fontes primárias são identificadas semanticamente; o sistema verifica referência literal e vínculos documentais, sem provar que todo documento é autêntico.

Com pouco material, o sistema responde ao que as fontes permitem e apresenta **análise preliminar**, com limitações e ACS reduzido. O estado interno continua `INCONCLUSIVE` quando não há condições de decisão definitiva; `assessment_level=preliminary` distingue essa resposta fundamentada de uma análise sem qualquer informação. Duas ou mais evidências diretas suficientes e independentes continuam podendo gerar decisões sustentadas ou contraditadas. Quantidade bruta de links não garante qualidade.

Domínios iguais, spans longos idênticos, textos próximos e cadeias documentais ligadas são agrupados conservadoramente. Conteúdo idêntico é deduplicado antes da qualificação. A mesma página tem uma unidade por alegação. Domínios diferentes não ganham independência automaticamente.

Para múltiplas alegações, o painel apresenta métricas individuais. Não publica uma média global sem comprovar comparabilidade e independência lógica. Uma alegação central contraditada não pode ser escondida por periféricas favoráveis. Cobertura incompleta bloqueia o resumo direcional global.

ESS/ACS são escalas de 0–100, **não probabilidades**. `null` aparece como “Indisponível”, acompanhado do motivo. Os indicadores circulares ficam fora do Markdown. Respostas antigas continuam legíveis, sem pontuações retroativas. O caminho JSON salva o mesmo resultado estruturado do SSE. A extensão embute `/chat`, portanto compartilha o painel e o contrato.

## Limites e custos

- Até quatro alegações, doze documentos ou sínteses citadas distintos e 24.000 caracteres para qualificação; até doze trechos qualificados. Fontes inacessíveis e formatos não textuais não recebem conteúdo inventado.
- Janelas contíguas de texto são selecionadas por sobreposição temática; offsets e hashes registram exatamente o material inspecionado. Leitura parcial é marcada, e não equivale a inspeção integral da fonte.
- Cada chamada semântica tem teto de saída: 3.000 tokens para extração, 6.000 para qualificação; recuperação tem teto de 1.800 e solicita achados com citações. Tokens de raciocínio estão incluídos no orçamento de saída do provedor.
- Até dezenove chamadas, deadline de análise de 140 segundos e timeout de até 30 segundos por chamada. Callbacks do SDK registram o uso antes da validação semântica, inclusive quando a etapa seguinte falha.
- Após 48.000 tokens observados, o sistema não inicia novas chamadas. **Isso é um limite de interrupção observado, não um teto monetário rígido:** chamadas já em voo e contexto interno de busca podem excedê-lo. Configure também controles de orçamento no projeto do provedor.
- Até duas análises e quatro chamadas ao modelo simultâneas por processo. Cada análise tem até quatro tarefas paralelas de recuperação. Em múltiplos workers/réplicas, dimensionar os limites totais na infraestrutura.
- Cache em memória somente dos documentos recuperados sem autenticação/cookies, por URL, até 64 entradas e cinco minutos. Não há cache compartilhado de perguntas, histórico, decisões ou dados privados de usuários.

A requisição continua autenticada e sujeita ao rate limit atômico do Mongo. Ruído local devolve a quota de análise, preservando a contagem de tráfego por minuto. Uma execução que já tentou usar o provedor consome a quota mesmo se falhar ou for cancelada; isso evita retentativas ilimitadas com gasto. Falhas de transporte podem não expor contagem de tokens: não são reportadas como uso conhecido zero. A API não faz retries automáticos pagos.

O streaming informa etapas enquanto pesquisa e calcula. O corpo é transmitido em fragmentos somente depois da decisão, usando o mesmo renderizador de Markdown durante e após a geração. Não há transmissão de raciocínio interno ou indicadores parciais. Não se usa atraso artificial entre fragmentos.

Buscas concluídas não são descartadas só porque a mensagem final do provedor ficou incompleta. São lidos eventos `web_search_call` e anotações SDK `url_citation`; links escritos livremente pelo modelo não bastam. A resposta e a auditoria registram consultas executadas, fontes localizadas, documentos inspecionados e sínteses usadas. Falha no download é distinguida de falta de resultados. Erros de configuração do provedor são operacionais, não ausência de evidência.

Quando uma página não pode ser lida, uma síntese associada à anotação de citação pode ser qualificada como `provider_excerpt`. Ela é identificada como síntese da busca, nunca como citação literal da página original ou prova de origem primária. Seu SQ é limitado a 0,5; quando necessário para a análise, seu uso limita o ACS a 25. Uma síntese complementar não penaliza prova direta suficiente. Se apenas esse material existir, o ESS continua indisponível, mas a resposta pode explicar os achados com a devida ressalva. Não há fallback para URLs ou conteúdo inventados sem metadados de busca observada.

Falhas operacionais não recebem veredito: autenticação do provedor, acesso ao modelo, conexão, limites e validação são reportados como erros próprios. O aviso de métricas não calculadas nesta versão é exclusivo de mensagens legadas concluídas. Se houver texto parcial antes de uma falha, a interface o marca como interrompido sem inventar classificação ou indicadores.

Se surgir `provider_authentication_failed`, confira `OPENAI_API_KEY` no processo do backend e no `.env` do projeto. Variáveis já exportadas pelo ambiente têm precedência sobre o arquivo. A credencial é da API do provedor, não o token Firebase do usuário. Após corrigir a configuração local, reinicie o backend. Não inclua valores de chaves em logs, mensagens ou capturas de tela.

Se a chave funciona em um processo novo, mas o Flask continua recusando após reinício, verifique exports antigos no terminal/IDE. O backend avisa quando `OPENAI_API_KEY`, `OPENAI_MODEL` ou `OPENAI_BASE_URL` herdados diferem do arquivo, sem registrar seus valores. Para iniciar localmente usando a chave e o modelo do `.env`, pare o servidor anterior e execute:

```bash
env -u OPENAI_API_KEY -u OPENAI_MODEL -u OPENAI_BASE_URL .venv/bin/python app.py
```

Isso limpa essas variáveis somente para o processo iniciado; não altera arquivos nem a precedência de configuração em produção.

## Segurança e retenção

Conteúdo de usuário, histórico e fontes não tem autoridade sobre parâmetros, scores ou ações. Contratos fechados rejeitam campos extras, números fora das rubricas, booleanos em atributos numéricos e dados ausentes disfarçados de score. URLs de fontes são limitadas aos resultados observados, e o servidor não usa cookies, proxies de ambiente ou credenciais para acessá-las.

O fetch valida hostname, esquema, porta e IPs de DNS; bloqueia redes internas/reservadas e endereços de metadata; fixa a conexão no IP público validado e verifica TLS com o hostname original. Revalida cada redirecionamento. Rejeita compressão e formatos não textuais; lê no máximo 512 KB. Páginas maiores recebem snapshot parcial explicitamente marcado, em vez de serem descartadas apenas pelo tamanho anunciado. O limite de concorrência DNS agora aguarda uma vaga por tempo limitado, em vez de descartar imediatamente fontes legítimas. Não executa JavaScript nem arquivos de fontes.

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

Em 15/11/2026, uma verificação real de uma afirmação pública confirmou quatro buscas executadas, fontes recebidas, documentos qualificados e resposta preliminar com ESS/ACS calculados. Esse smoke test verifica integração, não precisão estatística. Continuam necessárias avaliação de navegadores reais e a campanha científica de anotação/calibração/teste independente. A implementação não prova superioridade, precisão ou economia frente a outra IA. Para a banca, descreva-a como implementação candidata auditável, com resultados empíricos ainda separados da formulação matemática.
