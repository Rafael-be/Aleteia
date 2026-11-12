# Extensão Chrome da AleteIA

Esta pasta é uma extensão Manifest V3. Ela abre o próprio site em um iframe no
painel lateral nativo do Chrome, sem trocar a aba atual. O site continua responsável
pelo Firebase, histórico, respostas em streaming, limites de uso, conta e visual.
O layout se adapta à largura do painel usando o CSS responsivo existente.
Há um botão permanente para abrir `/chat` em uma nova aba.

## Instalar para testar, passo a passo

1. Use Chrome atualizado (mínimo 116).
2. Configure e execute o backend normalmente, conforme o README da raiz. A extensão
   não inicia Flask, MongoDB ou Firebase. O endereço local padrão é
   `http://127.0.0.1:5000`.
3. Abra `chrome://extensions`, ative **Modo do desenvolvedor** no canto superior
   direito e clique em **Carregar sem compactação**.
4. Selecione **somente esta pasta `extensions/chrome`**, que contém o manifesto da
   extensão. Não selecione a raiz nem o checkout aninhado `Aleteia/`.
5. Copie o **ID** exibido no cartão da extensão (32 letras).
6. Configure `CHROME_EXTENSION_IDS=ID_COPIADO` no ambiente do servidor e reinicie-o.
   Para vários IDs, separe com vírgulas. A aplicação lê variáveis do ambiente;
   só editar `.env` não basta se seu iniciador não carregar esse arquivo.
   No PowerShell, antes de `python app.py`, você pode executar:

   ```powershell
   $env:CHROME_EXTENSION_IDS = "cole_aqui_o_id_real"
   python app.py
   ```

7. Clique no ícone de quebra-cabeça do Chrome e no alfinete ao lado da AleteIA.
   Esse passo fixa o botão na barra superior; a extensão não pode fixá-lo sozinha.
8. Clique no botão AleteIA. O painel solicita login se não houver sessão nele.
   Use a sua conta do site. O login acontece ao abrir o painel pela primeira vez;
   a instalação não abre uma página automaticamente.
9. Envie uma mensagem e teste histórico, nova conversa, busca, conta e saída.
   Troque de aba e confirme que o painel continua disponível. Teste também
   **Abrir site em nova aba**. Arraste a borda do painel para ajustar sua largura.

## Usar com o site publicado

Em `config.js`, troque `SITE_URL` pelo endereço real HTTPS do seu site, sem `/chat`.
Depois recarregue a extensão no cartão de `chrome://extensions` e reabra o painel.
Configure o ID no ambiente do servidor publicado e publique também as alterações
de `src/utils/api.py`, `static/js/firebase-init.js` e `static/js/auth.js`.
Sem essa atualização do backend, a proteção `frame-ancestors` bloqueia o painel.
Se houver proxy/CDN configurando CSP ou `X-Frame-Options`, ajuste-o também para
autorizar a extensão específica, preservando a proteção para outros sites.

## Login e limitações que precisam de teste real

O painel usa as mesmas páginas de autenticação do site; senhas e tokens não são
enviados ao código da extensão. A sessão pode ficar separada da aba normal por
causa do particionamento de armazenamento do Chrome. Entrar na aba normal não
garante entrar no painel. Bloqueios de armazenamento também podem afetar Firebase.

Teste e-mail/senha e cada provedor social usado no projeto. Google, GitHub e
Microsoft podem impor restrições a contextos incorporados/popups. Se um provedor
bloquear esse contexto, e-mail/senha é a alternativa no painel; abrir o site é a
alternativa para usar o provedor, sem garantia de transferir a sessão ao painel.
Um fluxo OAuth próprio da extensão exigiria outra integração e configuração nos
provedores. A equivalência completa de funcionamento só pode ser confirmada no
Chrome com seu domínio e Firebase reais. Não foi automatizada neste projeto.

## Organização e atualizações

Recomendação: mantenha esta pasta no mesmo repositório do site. Assim as mudanças
de autenticação, segurança e extensão podem ser revisadas juntas. A extensão é um
pacote separado e tem seu próprio `manifest.json`; o manifesto da raiz permanece
independente. Não copie templates, CSS e JavaScript do chat para a extensão:
ela recebe as atualizações do site quando o painel é carregado novamente.

Alterações no pacote da extensão precisam de recarregamento na instalação local
ou de uma nova versão na loja. Um repositório separado faz sentido se houver
equipe e ciclo de releases independentes; isso não melhora compatibilidade por si.

## Distribuir para outras pessoas

Para desenvolvimento, cada pessoa pode carregar a pasta sem compactação e você
autoriza seu ID no servidor. Não presuma que IDs de instalações locais serão iguais.
Para distribuição pública, prepare uma publicação na Chrome Web Store, revise suas
políticas atuais, forneça os materiais/declarações solicitados e gere um ZIP com
o conteúdo desta pasta (o `manifest.json` precisa estar na raiz do ZIP).
Autorize no servidor o ID atribuído à extensão da loja antes de distribuir.
Nunca inclua `.env`, service account, chaves privadas ou o backend nesse ZIP.

As permissões são `sidePanel` (painel), `contextMenus` (ação sobre o texto selecionado)
e `storage` (fila temporária na memória do navegador). Não há acesso permanente aos
sites, leitura do restante da página, nem leitura da área de transferência. O botão
de nova aba usa `tabs.create`, que não exige a permissão `tabs`.

## Enviar um trecho selecionado

1. Em uma página HTTP/HTTPS, selecione um texto e clique com o botão direito.
2. Escolha **Enviar texto à AleteIA**. Essa ação autoriza enviar o trecho à IA,
   consumindo o limite normal da conta e salvando-o no histórico como uma mensagem.
3. O painel abre e envia o texto na conversa atual. Se necessário, entre na conta
   e confirme o e-mail primeiro. Uma resposta em andamento ou um rascunho existente
   fazem o trecho aguardar; o rascunho não é sobrescrito.

É possível cancelar textos ainda pendentes pelo botão exibido no painel. Isso não
cancela mensagens já enviadas. Cada seleção aceita até 12.000 caracteres; trechos
maiores são recusados, sem corte silencioso. Vários trechos aguardam em ordem por
janela. Seleções pendentes expiram para envio após dez minutos. A fila usa
`storage.session`, sem sincronização nem persistência em disco, e é removida ao
entregar o texto, fechar a janela ou encerrar a sessão do navegador.

O texto não é colocado na URL nem nos logs da extensão. A comunicação entre painel
e site valida a origem e a janela remetente nos dois lados, e o site só aceita IDs
configurados em `CHROME_EXTENSION_IDS`. Tokens e senhas continuam no fluxo Firebase
do site. O backend continua verificando token, conta, limites e acesso às conversas.

Para ativar a versão 1.1.0, publique também o template do chat, `app.py`,
`static/js/chat.js` e `static/js/extension-selection.js` no servidor; recarregue a
extensão em `brave://extensions` ou `chrome://extensions` e reabra o painel.
Na loja, envie um novo pacote e atualize as declarações de permissões e privacidade
para mencionar o envio explícito de seleções. Teste com duas janelas, login pendente,
rascunho, resposta em andamento e recarregamento. Páginas internas do navegador não
oferecem esse fluxo; não há OCR de imagens. É necessária conexão com o servidor.
