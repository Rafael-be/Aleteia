# AleteIA

Este é um projeto de pesquisa relacionado ao curso técnico em informática integrado ao ensino médio da Escola Técnica Estadual Monteiro Lobato, com finalidade unicamente acadêmica, sendo desenvolvido por Rafael Nascimento Bê e Theo Keller Paiva.

O projeto se norteia pela descoberta e validação do problema da fácil propagação das fake news nos dias de hoje, devido à pluralização das redes sociais, principal meio de comunicação de informações atualmente.

Por isso, a proposta feita foi o desenvolvimento de um software capaz de ler um input, em texto ou imagem, e submetê-lo a uma série de testes academicamente comprovados, através de uma IA aplicada. O software contará com um site para inserir o input e uma extensão para acesso mais fácil e rápido, com menos informações e com um botão de redirecionamento para o site, onde será possível ver mais informações sobre o porquê do veredito.

## Visão geral

A Aleteia combina:

- backend em Python com Flask;
- autenticação via JWT;
- banco de dados MongoDB;
- interface web em HTML, CSS e JavaScript;
- integração com a API da OpenAI para geração de respostas com base em contexto e busca web.

O projeto foi pensado como ferramenta de apoio ao estudo de desinformação, com finalidade acadêmica e experimental.

## Tecnologias utilizadas

### Backend

- Python 3
- Flask
- MongoDB
- PyMongo
- PyJWT
- bcrypt
- python-dotenv
- OpenAI Python SDK

### Frontend

- HTML5
- CSS
- JavaScript
- Templates Jinja

### Infraestrutura e utilidades

- Arquivos de ambiente com `.env`
- Sessões do Flask para controle de autenticação
- Limite diário de uso por usuário

## Funcionalidades atuais

- Cadastro de usuários
- Login com autenticação JWT
- Proteção de rotas autenticadas
- Histórico de conversas por usuário
- Envio de mensagens para a IA
- Geração de resposta estruturada em português
- Persistência de prompt e resposta no banco
- Limitação diária de uso por usuário

## Requisitos

- Python 3.10 ou superior
- MongoDB local ou remoto acessível
- Chave da API OpenAI

## Configuração do ambiente

1. Crie um ambiente virtual:

```bash
python -m venv venv
```

2. Ative o ambiente virtual:

- Linux/macOS:

```bash
source venv/bin/activate
```

- Windows:

```bash
venv\Scripts\activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Crie um arquivo `.env` com base no `Exemplo.env`.

5. Defina as variáveis de ambiente:

```env
MONGO_URI=sua_string_de_conexao_mongodb
MONGO_DB_NAME=nome_do_banco
JWT_SECRET_KEY=sua_chave_secreta
SECRET_KEY=sua_chave_de_sessao
OPENAI_API_KEY=sua_chave_openai
OPENAI_MODEL=gpt-5.6-terra
TOKENS_LIMITE_DIARIO_USUARIO=50000
```

> O arquivo `Exemplo.env` pode ser usado como referência para preencher as variáveis necessárias.
> Antes de iniciar a aplicação, o responsável pela execução deve escolher o modelo de IA que será usado e também definir o limite diário de tokens conforme sua necessidade e orçamento.
> O valor de `TOKENS_LIMITE_DIARIO_USUARIO` é configurável e pode ser ajustado para qualquer valor desejado, de acordo com os critérios do ambiente em que o projeto será executado.

## Execução local

```bash
python app.py
```

Por padrão, a aplicação será iniciada em:

```text
http://127.0.0.1:5000
```

## Deploy

O projeto também foi publicado em ambiente de demonstração na web em:

```text
https://aleteia.onrender.com
```

Essa versão pública serve como ambiente de apresentação do sistema, permitindo acesso ao fluxo principal da aplicação em um deploy externo para testes e demonstração do projeto.

## Estrutura do projeto

```text
Aleteia/
├── app.py
├── README.md
├── requirements.txt
├── Exemplo.env
├── manifest.json
├── public/
│   ├── cadastroTeste/
│   │   └── cadastro.html
│   ├── chat/
│   │   └── chatIndex.html
│   ├── index/
│   │   └── popup.html
│   ├── login/
│   │   └── login.html
│   └── main/
│       ├── main-desktop.html
│       └── main-mobile.html
├── src/
│   ├── controller/
│   │   ├── chatController.py
│   │   ├── gemini_controller.py
│   │   └── userController.py
│   ├── models/
│   │   ├── chatModel.py
│   │   └── userModel.py
│   ├── routes/
│   │   ├── chatRoutes.py
│   │   └── userRoutes.py
│   ├── services/
│   │   ├── gemini_services.py
│   │   └── openai_services.py
│   └── utils/
│       └── token_limiter.py
├── static/
│   ├── css/
│   ├── images/
│   └── js/
└── query/
```

## Fluxo da aplicação

### Autenticação

1. O usuário acessa a rota `/cadastro` para criar conta.
2. O frontend envia os dados para `POST /api/users/register`.
3. O usuário faz login em `POST /api/users/login`.
4. A API retorna um token JWT.
5. O token é enviado no header `Authorization` para rotas protegidas.

Formato esperado:

```http
Authorization: Bearer <token>
```

### Chat

1. O usuário acessa `/chat` após autenticação.
2. O frontend envia a mensagem para `POST /api/chat/mensagem`.
3. O backend valida o token, verifica limites e chama a IA.
4. A resposta é salva junto ao prompt no MongoDB.
5. O histórico pode ser consultado em `GET /api/chat/conversas`.

## API

### Usuários

#### `POST /api/users/register`

Cria um novo usuário.

Body esperado:

```json
{
  "email": "usuario@email.com",
  "password": "Senha123",
  "confirm_password": "Senha123"
}
```

Respostas possíveis:

- `201`: cadastro realizado com sucesso
- `400`: corpo da requisição inválido
- `422`: regra de validação violada
- `500`: erro interno do servidor

#### `POST /api/users/login`

Autentica um usuário e retorna um JWT.

Body esperado:

```json
{
  "email": "usuario@email.com",
  "password": "Senha123"
}
```

Respostas possíveis:

- `200`: login concluído com sucesso
- `400`: dados ausentes ou inválidos
- `401`: credenciais inválidas
- `403`: conta desativada
- `422`: falha em validações
- `500`: erro interno do servidor

### Chat

#### `POST /api/chat/mensagem`

Envia uma mensagem do usuário para a IA e salva o histórico da conversa.

Headers:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Body esperado:

```json
{
  "conversa_id": "uuid-da-conversa",
  "prompt": "Texto que deseja verificar"
}
```

Respostas possíveis:

- `200`: resposta da IA gerada com sucesso
- `400`: prompt vazio ou conversa_id ausente
- `401`: token ausente ou inválido
- `429`: limite diário excedido
- `502`: falha ao chamar a OpenAI

#### `GET /api/chat/conversas`

Retorna as conversas do usuário autenticado.

Headers:

```http
Authorization: Bearer <token>
```

#### `GET /api/chat/conversas/<conversa_id>`

Retorna todas as mensagens de uma conversa específica.

Headers:

```http
Authorization: Bearer <token>
```

## Observações importantes

- A extensão em `manifest.json` existe como protótipo inicial, mas não está integrada ao fluxo completo da aplicação.
- O projeto está em desenvolvimento acadêmico, portanto alguns elementos da interface podem representar versões experimentais ou recursos em expansão.
- O backend atual foi implementado com a OpenAI como motor principal de análise de fato, e não depende de bibliotecas locais de NLP para o funcionamento principal.
- O arquivo `src/routes/chatRoutes.py` mantém rotas antigas do Gemini como referência histórica, mas elas não são registradas em `app.py` no fluxo atual.
- O modelo de IA pode ser selecionado conforme a preferência e disponibilidade do ambiente: o projeto aceita ajuste da variável `OPENAI_MODEL`, e o modelo atual configurado no exemplo é `gpt-5.6-terra`.
- O limite diário de tokens também deve ser definido pelo responsável pela execução, conforme o orçamento e a necessidade de uso do sistema.

## Status do projeto

Este projeto está em evolução e foi estruturado como um sistema de demonstração funcional para validação de uso em contexto acadêmico, com foco em:

- autenticação de usuários;
- integração com IA para verificação de textos;
- histórico de conversas;
- experiência web simples e direta.


