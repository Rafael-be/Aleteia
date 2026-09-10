# AleteIA

## Autenticação

A autenticação é feita pelo Firebase Authentication. O backend nunca recebe nem
armazena senhas: ele valida ID tokens do Firebase e usa o `firebase_uid` para
encontrar os dados de negócio no MongoDB.

Antes de iniciar, copie `.env.example` para `.env` e configure:

- `FIREBASE_SERVICE_ACCOUNT_JSON`: conteúdo completo da Service Account, em uma
  única variável. Nunca versione esse valor.
- `FIREBASE_WEB_CONFIG_JSON`: objeto de configuração Web do Firebase. Apesar de
  público, é mantido no ambiente para não fixar um projeto no código.

No Firebase Console, habilite E-mail/senha, Google, GitHub e Microsoft. Para os
dois últimos, configure também as credenciais OAuth do respectivo provedor.

## Fluxo

1. O navegador cadastra/autentica diretamente com o Firebase.
2. Contas de e-mail recebem o link de confirmação do Firebase.
3. Após login confirmado, o navegador chama `POST /api/auth/sincronizar` com o
   ID token; o Mongo cria o perfil gratuito caso ainda não exista.
4. As rotas do chat verificam token e `email_verified` no backend.
5. O Mongo aplica limite diário de 10 perguntas e registra os tokens usados.

## Desenvolvimento

```bash
pip install -r requirements.txt
python app.py
```

Para validar o fluxo completo, cadastre uma conta, confirme o e-mail, faça login,
envie mensagens até o limite diário e confirme as respostas 403 (e-mail não
verificado) e 429 (limite atingido).
