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

A única permissão pedida é `sidePanel`. A extensão não lê a página visitada e não
precisa de acesso a todos os sites. O botão de nova aba usa `tabs.create`, que não
exige a permissão `tabs`. É necessária conexão com o servidor; não há modo offline.
