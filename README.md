# AleteIA

Este é um projeto de pesquisa relacionado ao curso técnico em informática integrado ao ensino médio da Escola Técnica Estadual Monteiro Lobato, com finalidade unicamente acadêmica, sendo desenvolvido por Rafael Nascimento Bê e Theo Keller Paiva.

O projeto se norteia pela descoberta e validação do problema da fácil propagação das fake news nos dias de hoje, devido à pluralização das redes sociais, principal meio de comunicação de informações atualmente.

Por isso, a proposta feita foi o desenvolvimento de um software capaz de ler um input, em texto ou imagem, e submetê-lo a uma série de testes academicamente comprovados, através de uma IA aplicada. O software contará com um site para inserir o input e uma extensão para acesso mais fácil e rápido, com menos informações e com um botão de redirecionamento para o site, onde será possível ver mais informações sobre o porquê do veredito.

## Ferramentas e tecnologias

### Backend

**Python:** linguagem de programação usada no backend do projeto. É uma linguagem poderosa, escalável e completa, com bibliotecas robustas, como Scikit-learn, NLTK e Spacy, que facilitam o desenvolvimento de sistemas com inteligência artificial e Processamento de Linguagem Natural (NLP).

**Flask:** framework usado para estruturar o backend, criar rotas, renderizar páginas e disponibilizar endpoints de API. Ele conversa bem com aplicações de NLP e com a futura integração de IA do projeto.

**MongoDB:** banco de dados usado para armazenar usuários e histórico de prompts.

**JWT:** usado para autenticação. Depois do login, o backend gera um token que o frontend salva no `localStorage` e envia nas rotas protegidas.

### Frontend

**HTML5:** usado para estruturar as páginas, formulários e elementos principais da interface.

**CSS e Bootstrap:** usados para estilização visual, responsividade e componentes básicos de interface.

**JavaScript:** usado para controlar interações da interface, autenticação no frontend, envio de prompts e carregamento do histórico de conversas.

## Como rodar o projeto

1. Crie e ative um ambiente virtual:

```bash
python -m venv venv
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Crie um arquivo `.env` com base no `Exemplo.env`.

4. Configure as variáveis:

```env
MONGO_URI=sua_string_de_conexao_mongodb
MONGO_DB_NAME=nome_do_banco
JWT_SECRET_KEY=sua_chave_secreta
```

5. Execute a aplicação:

```bash
python app.py
```

Por padrão, o Flask inicia em `http://127.0.0.1:5000`.

## Estrutura do projeto

```text
Aleteia/
├── app.py
├── README.md
├── requirements.txt
├── Exemplo.env
├── css/
│   ├── style.css
│   ├── auth.css
│   └── chat.css
├── images/
├── js/
│   ├── main.js
│   ├── auth.js
│   └── chat.js
├── public/
│   ├── main/
│   ├── login/
│   ├── cadastroTeste/
│   ├── chat/
│   └── index/
└── src/
    ├── controller/
    ├── models/
    └── routes/
```

## Páginas

| Rota | Arquivo | Função |
| --- | --- | --- |
| `/` | `public/main/main-desktop.html` | Página inicial do site, com apresentação da AleteIA, sidebar e botão para iniciar o chat. |
| `/login` | `public/login/login.html` | Tela de login. Envia e-mail e senha para a API de autenticação. |
| `/cadastro` | `public/cadastroTeste/cadastro.html` | Tela de cadastro. Cria usuário e tenta realizar login automático. |
| `/chat` | `public/chat/chatIndex.html` | Tela de envio de prompts e visualização do histórico de conversas do usuário logado. |

Observação: `public/main/main-mobile.html` existe como versão/protótipo mobile separado, mas a rota principal atual usa `main-desktop.html`, que já possui comportamento responsivo.

## Extensão

A extensão ainda está em fase de protótipo.

O arquivo `manifest.json` aponta para `public/index/popup.html` como popup da extensão. Essa tela representa uma versão simples para envio de input, mas ainda não está integrada ao fluxo completo do site nem às APIs finais de verificação.

## Fluxo de autenticação

1. O usuário cria uma conta em `/cadastro`.
2. O frontend envia os dados para `POST /api/users/register`.
3. Depois do cadastro, o frontend tenta autenticar o usuário em `POST /api/users/login`.
4. A API retorna um token JWT.
5. O frontend salva o token no `localStorage`.
6. As rotas protegidas do chat usam o header:

```http
Authorization: Bearer <token>
```

## API de usuários

### `POST /api/users/register`

Cadastra um novo usuário.

Body esperado:

```json
{
  "email": "usuario@email.com",
  "password": "Senha123",
  "confirm_password": "Senha123"
}
```

Possíveis respostas:

| Status | Significado |
| --- | --- |
| `201` | Usuário cadastrado com sucesso. |
| `400` | Corpo inválido ou campos obrigatórios ausentes. |
| `422` | Regra de validação violada, como e-mail inválido, senha fraca ou senhas diferentes. |
| `500` | Erro interno no servidor. |

### `POST /api/users/login`

Autentica um usuário e retorna um token JWT.

Body esperado:

```json
{
  "email": "usuario@email.com",
  "password": "Senha123"
}
```

Possíveis respostas:

| Status | Significado |
| --- | --- |
| `200` | Login realizado com sucesso. Retorna o token JWT. |
| `400` | Corpo inválido ou campos obrigatórios ausentes. |
| `401` | Credenciais inválidas. |
| `403` | Conta desativada. |
| `422` | Falha nas validações de formato. |
| `500` | Erro interno no servidor. |

## API de chat

As rotas de chat exigem autenticação por JWT.

### `POST /api/chat/prompt`

Salva um prompt no histórico do usuário logado.

Headers:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Body esperado:

```json
{
  "prompt": "Texto que o usuário deseja verificar"
}
```

Possíveis respostas:

| Status | Significado |
| --- | --- |
| `201` | Prompt salvo com sucesso. |
| `400` | Prompt vazio ou inválido. |
| `401` | Token ausente ou inválido. |

### `GET /api/chat/prompts`

Retorna o histórico de prompts do usuário logado, ordenado do mais recente para o mais antigo.

Headers:

```http
Authorization: Bearer <token>
```

Possíveis respostas:

| Status | Significado |
| --- | --- |
| `200` | Histórico retornado com sucesso. |
| `401` | Token ausente ou inválido. |

## Observações de desenvolvimento

- O botão de anexar arquivo e o botão de microfone aparecem na interface do chat, mas ainda não possuem implementação completa.
- Os botões de login com Google e Microsoft aparecem na tela de login, mas ainda não possuem autenticação integrada.
- O JavaScript do chat atualmente redireciona para `/conversa?q=...` após salvar o prompt, porém essa rota ainda não está registrada em `app.py`.
- O projeto ainda está em desenvolvimento acadêmico, então algumas telas e fluxos podem representar protótipos ou funcionalidades futuras.
