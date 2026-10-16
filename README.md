# G7M

Sistema multiempresa G7M (anteriormente Gym Presence) para gestão de ginásios, planos, clientes, assinaturas e presenças. O frontend está em `frontend/`; `/docs` contém a documentação interativa da API FastAPI.

Para entender o fluxo full-stack, as relações entre dados, os endpoints e os limites operacionais, consulte [FLUXO_DO_SISTEMA.md](./FLUXO_DO_SISTEMA.md).

## Início rápido

Com a API em execução, use:

```text
Base URL: http://127.0.0.1:8000
Swagger:  http://127.0.0.1:8000/docs
OpenAPI:  http://127.0.0.1:8000/openapi.json
```

O banco ativo fica em `%LOCALAPPDATA%\GymPresence\gym_presence.db` no Windows ou `~/.local/share/gym-presence/gym_presence.db` em macOS/Linux. Uma instalação nova não cria contas ou dados de demonstração automaticamente. O primeiro cadastro cria a empresa, a conta administrativa e o primeiro ginásio. Na atualização de uma base anterior, os registros existentes são preservados e agrupados na empresa `Empresa migrada`.

## Configuração para desenvolvimento

Instale as dependências e prepare a base local:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\configurar_sqlite.py
```

Use sempre o interpretador dentro de `.venv` para instalar dependências e iniciar a API. Isso evita que o VS Code, o terminal e o Uvicorn usem instalações Python diferentes. Python 3.14 estável é suportado. A preparação da base é feita uma vez e não é repetida pelo script de arranque.

Para confirmar qual interpretador está em uso:

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.version)"
.\.venv\Scripts\python.exe -m uvicorn --version
```

Se o recarregamento automático causar problemas no ambiente local, execute sem `--reload`; isso remove somente o monitor de arquivos, não altera o código da API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O CORS local já permite `http://127.0.0.1:5500`, `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000` e `http://127.0.0.1:3000`. Para outros hosts/portas, configure `FRONTEND_ORIGINS` no `.env` como uma lista separada por vírgulas de origens completas, por exemplo:

```env
FRONTEND_ORIGINS=http://localhost:5173,https://frontend.exemplo.pt
```

Não use `*` em produção. A allowlist autoriza `GET`, `POST`, `PUT`, `PATCH`, `OPTIONS` e os cabeçalhos `Content-Type` e `X-Admin-Token`.

### Interface web local

O frontend é uma SPA React/TypeScript. Requer Node.js 20.19+, 22.12+ ou 24+. Instale as dependências uma vez:

```text
cd frontend
npm install
```

Depois de preparar o backend e instalar as dependências do frontend, inicie ambos a partir da raiz do repositório:

```powershell
.\.venv\Scripts\python.exe scripts\dev.py
```

O comando abre a API em `http://127.0.0.1:8000` e o frontend em `http://127.0.0.1:5173`; prima `Ctrl+C` para encerrar ambos. Em macOS/Linux, execute `python scripts/dev.py` com o ambiente virtual activo. O script prefere automaticamente o interpretador `.venv` e não instala pacotes nem altera a base de dados. Crie a conta em **Criar conta da empresa**; o registo cria atomicamente a empresa, o administrador e o primeiro ginásio. Na aplicação autenticada é possível actualizar o perfil, gerir ginásios e planos, e registar clientes associados a um plano. Os endereços antigos `login.html`, `signup.html`, `clientes.html` e `planos.html` redireccionam para as respectivas páginas da SPA.

Se as portas padrão já estiverem ocupadas, indique alternativas, por exemplo `.\.venv\Scripts\python.exe scripts\dev.py --api-port 8001 --frontend-port 5174`.

Para gerar os ficheiros de produção, execute `npm run build` na pasta `frontend`; o resultado fica em `frontend/dist`. O endereço da API pode ser definido durante o build com `VITE_API_URL`; por omissão, usa `http://127.0.0.1:8000`. A sessão continua apenas enquanto a aplicação está aberta: o token é mantido em memória e não é gravado no navegador; recarregar a página exige novo login, pois a API ainda não oferece renovação de sessão.

As fontes Archivo e Source Sans 3 são subconjuntos locais em WOFF2; as licenças OFL ficam em `frontend/public/licenses`. Execute `npm test` e `npm run typecheck` na pasta `frontend` para validar a interface.

O projeto usa SQLite local e limita `APP_ENV` a `development` e `test`; esta configuração não é uma implantação multi-instância pronta para produção.

### Experimento de plano de controlo e provisionamento

Há uma primeira fatia isolada da Fase 0 em `app/data/control_plane.py`, `app/data/tenant_databases.py` e `app/services/provisionamento.py`. Ela cria metadados centrais e uma base SQLite separada por empresa, regista estados de provisionamento e permite repetir com segurança o cadastro inicial do proprietário e do ginásio. Os testes usam diretórios temporários.

Este caminho ainda não está ligado às rotas, autenticação ou repositório usado pela aplicação; não altera nem migra `gym_presence.db`. O schema tenant versão 2 contém ginásio, membros da equipa, planos, clientes, assinaturas, credenciais, presenças e auditoria. As restrições garantem um ginásio por empresa, cliente associado a uma assinatura/plano da mesma base, um administrador ativo, referências únicas dentro do tenant, presenças sem eliminação e anulação justificada, e auditoria append-only. Os dados originais da presença não podem ser alterados; o fecho e a anulação são campos separados.

As entradas `dados_antes` e `dados_depois` da auditoria são destinadas a metadados mínimos e redigidos; não devem incluir palavras-passe, tokens, credenciais, NIF, documentos ou telefones em claro. O provisionador recusa bases existentes com versão ou tabelas divergentes: não existe migração automática nesta fatia. Não usar em produção: PostgreSQL, credenciais de privilégio mínimo, migrações versionadas completas e integração com sessões continuam pendentes.

## Convenções HTTP

- Envie e receba JSON com `Content-Type: application/json`.
- Use os caminhos exatamente como documentados, sem barra final.
- Datas são ISO 8601. Envie sempre timezone, preferencialmente UTC (`Z` ou `+00:00`).
- IDs são strings opacas; não os monte no frontend.
- Coleções são arrays JSON. A API ainda não implementa paginação.
- Erros FastAPI usam `{ "detail": ... }`; validações `422` podem retornar uma lista estruturada em `detail`.

## Autenticação admin

O cadastro inicial público cria uma empresa, o administrador proprietário e o primeiro ginásio numa única transação. Depois disso, faça `POST /admin/login` com o email administrativo e a palavra-passe escolhidos no cadastro:

```json
{
  "email": "administrador@example.com",
  "password": "palavra-passe-definida-no-cadastro"
}
```

Resposta `200`:

```json
{
  "access_token": "<token-assinado>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Envie `access_token` no cabeçalho `X-Admin-Token` nas rotas admin:

```http
X-Admin-Token: <access_token>
```

O token expira em uma hora. Não há refresh token nem endpoint de logout: descarte o token no cliente ao sair ou receber `401` e solicite novo login. Como o backend usa um token próprio, não envie `Authorization: Bearer`; o cabeçalho esperado é `X-Admin-Token`.

Recomendação para o frontend: mantenha o token em memória da aplicação. Evite `localStorage`/`sessionStorage` se não forem necessários, nunca registre o token em logs e não o coloque na URL. Login inválido retorna `401` com `detail: "Email ou senha inválidos."`.

### Exemplo TypeScript

```ts
const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

type AdminSession = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

async function login(email: string, password: string): Promise<AdminSession> {
  const response = await fetch(`${API_URL}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await readApiError(response);
  return response.json();
}

async function adminFetch<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token,
      ...init.headers,
    },
  });
  if (!response.ok) throw await readApiError(response);
  return response.json();
}

async function readApiError(response: Response) {
  const body = await response.json().catch(() => ({}));
  return new Error(body.detail ?? `Falha HTTP ${response.status}`);
}
```

`adminFetch` é para rotas protegidas, incluindo a marcação manual de presença. O cadastro da empresa, o login e os endpoints de saúde são públicos; os restantes dados são privados ao tenant do token. Não defina `credentials: "include"`; a autenticação usa token em header, não cookie.

## Endpoints e autorização

| Método | Caminho | Auth | Sucesso | Uso |
| --- | --- | --- | --- | --- |
| `GET` | `/health/live` | Pública | `200` | Processo HTTP ativo. |
| `GET` | `/health/ready` | Pública | `200` | SQLite acessível e schema completo. |
| `POST` | `/admin/register` | Pública | `201` | Criar empresa, primeiro administrador e primeiro ginásio. |
| `POST` | `/admin/login` | Pública | `200` | Login e emissão de token. |
| `GET` | `/empresa` | Admin | `200` | Consultar o perfil da empresa do token. |
| `PATCH` | `/empresa` | Admin | `200` | Atualizar o perfil da empresa do token. |
| `GET` | `/ginasios` | Admin | `200` | Listar somente os ginásios da empresa. |
| `POST` | `/ginasios` | Admin | `201` | Criar ginásio. |
| `GET` | `/planos` | Admin | `200` | Listar somente os planos da empresa. |
| `GET` | `/planos/{plano_id}` | Admin | `200` | Consultar plano da empresa. |
| `POST` | `/planos` | Admin | `201` | Criar plano. |
| `PUT` | `/planos/{plano_id}` | Admin | `200` | Substituir regras completas do plano. |
| `GET` | `/clientes` | Admin | `200` | Listar clientes. |
| `GET` | `/clientes/{cliente_id}` | Admin | `200` | Cliente, plano e uso. |
| `POST` | `/clientes` | Admin | `201` | Registar cliente e credenciais. |
| `PATCH` | `/clientes/{cliente_id}/assinatura` | Admin | `200` | Atualizar campos de assinatura enviados. |
| `POST` | `/presencas/marcar` | Admin | `200` | Marcar entrada ou saída por credencial no ginásio da empresa autenticada. |
| `GET` | `/presencas` | Admin | `200` | Consultar histórico. |

## Tipos e payloads

### Cadastro inicial da empresa

`POST /admin/register` cria o tenant, a conta do administrador e o primeiro ginásio. O email administrativo deve ser único na plataforma; a palavra-passe precisa ter pelo menos 12 caracteres.

```json
{
  "empresa": {
    "nome": "Ginásio Exemplo, Lda.",
    "email": "contacto@example.com",
    "telefone": "210000000",
    "endereco": "Rua Principal, 10"
  },
  "administrador": {
    "email": "admin@example.com",
    "password": "uma-palavra-passe-forte"
  },
  "ginasio": {
    "nome": "Unidade Centro",
    "endereco": "Rua Principal, 10"
  }
}
```

A resposta inclui os dados criados e um token administrativo. A interface web não persiste o token entre páginas; depois do cadastro, entre com as mesmas credenciais. `GET/PATCH /empresa` só lê ou altera o perfil associado ao token.

### Ginásio

`POST /ginasios` exige autenticação administrativa e associa o ginásio à empresa do token:

```json
{
  "nome": "Ginásio Centro",
  "endereco": "Av. Principal, 100"
}
```

Resposta: `{ "id": "gym-...", "nome": "Ginásio Centro", "endereco": "Av. Principal, 100" }`.

### Plano

`POST /planos` e `PUT /planos/{plano_id}` usam:

```json
{
  "nome": "Básico",
  "descricao": "Até três visitas por semana",
  "max_visitas_semana": 3,
  "max_visitas_mes": 12,
  "hora_inicio": "08:00:00",
  "hora_fim": "18:00:00",
  "dias_semana": [0, 1, 2, 3, 4, 5],
  "duracao_maxima_minutos": 90,
  "ginasios_permitidos": ["gym-centro"],
  "ativo": true
}
```

| Campo | Tipo | Regra |
| --- | --- | --- |
| `id` | string | Só na resposta; gerado pelo backend. |
| `nome` | string | Obrigatório, entre 1 e 100 caracteres. |
| `descricao` | string | Opcional; padrão `""`. |
| `max_visitas_semana` | integer ou `null` | Inteiro >= 0; `null` não impõe limite. |
| `max_visitas_mes` | integer ou `null` | Inteiro >= 0; `null` não impõe limite. |
| `hora_inicio`, `hora_fim` | hora `HH:MM:SS` ou `null` | Se ambas existirem, início < fim. |
| `dias_semana` | array de inteiros | Únicos, de 0 (segunda) a 6 (domingo). |
| `duracao_maxima_minutos` | integer ou `null` | Maior que zero ou sem limite (`null`). |
| `ginasios_permitidos` | array de strings | Um ou mais IDs de ginásios pertencentes à empresa autenticada; IDs externos e lista vazia são rejeitados. |
| `ativo` | boolean | Padrão `true`. |

`PUT` substitui a representação inteira; campos omitidos voltam aos padrões do schema. `PATCH` não é usado para edição de plano.

### Cliente

`POST /clientes`:

```json
{
  "nome": "Ana Costa",
  "email": "ana@example.com",
  "telefone": "910000000",
  "plano_id": "plano-basico",
  "assinatura_inicio": "2026-10-10T00:00:00Z",
  "assinatura_fim": "2026-11-10T00:00:00Z",
  "credenciais": [
    { "metodo": "cartao", "codigo": "CARD-ANA-001" }
  ]
}
```

| Campo | Tipo | Regra |
| --- | --- | --- |
| `id` | string | Só na resposta; gerado pelo backend. |
| `nome` | string | Obrigatório, entre 1 e 120 caracteres. |
| `email` | string | Obrigatório, formato de email; normalizado para minúsculas. |
| `telefone` | string | Opcional; padrão `""`. |
| `plano_id` | string | Obrigatório; plano ativo pertencente à empresa e associado a pelo menos um ginásio. |
| `assinatura_inicio`, `assinatura_fim` | datetime ISO 8601 | Mesmo padrão de timezone; início < fim. |
| `credenciais` | array | Cada item tem `metodo` e `codigo`; padrão `[]`. |
| `ativo` | boolean | Só na resposta; padrão `true`. |

Métodos de credencial aceitos: `biometria`, `face`, `cartao`, `pin` e `qr`. Emails e pares (`metodo`, `codigo`) são únicos dentro de cada empresa; empresas distintas podem usar os mesmos valores.

Resposta de `GET /clientes/{cliente_id}` inclui o cliente mais:

```json
{
  "plano": { "id": "plano-basico", "nome": "Básico" },
  "uso_plano": {
    "visitas_semana": 1,
    "max_visitas_semana": 3,
    "restantes_semana": 2,
    "visitas_mes": 2,
    "max_visitas_mes": 12,
    "restantes_mes": 10,
    "horario": { "inicio": "08:00", "fim": "18:00" },
    "dias_semana": [0, 1, 2, 3, 4, 5],
    "duracao_maxima_minutos": 90
  }
}
```

Os números acima são ilustrativos; `null` em máximo/restantes significa sem limite.

### Atualizar assinatura

`PATCH /clientes/{cliente_id}/assinatura` aceita um ou mais campos:

```json
{
  "plano_id": "plano-premium",
  "assinatura_fim": "2027-10-10T00:00:00Z"
}
```

Campos não enviados são preservados. Enviar `{}` retorna `422`. A API valida novamente plano e intervalo final resultante.

### Presença

`POST /presencas/marcar`:

```json
{
  "ginasio_id": "gym-centro",
  "metodo": "cartao",
  "credencial": "CARD-ANA-001",
  "tipo": "entrada"
}
```

Envie também o cabeçalho `X-Admin-Token` da sessão administrativa. O ginásio tem de pertencer à empresa dessa sessão; um ginásio de outra empresa responde `404`. Não envie `empresa_id`: o servidor obtém o tenant exclusivamente da sessão. A entrada pública de eventos de dispositivos ainda não está implementada.

`tipo` aceita `entrada`, `saida` ou `null`/omitido. Sem `tipo`, a API fecha uma presença aberta; se não houver, tenta abrir entrada. A resposta de entrada informa `autorizado`, `tipo`, mensagem, cliente, plano, ginásio, método, `entrada_em` e `uso_plano`. A resposta de saída inclui também `saida_em`, `duracao_minutos` e `aviso`.

## Fluxo recomendado para o frontend

1. Criar a empresa, o administrador e o primeiro ginásio em `POST /admin/register` ou na interface web.
2. Fazer login em `POST /admin/login` e manter `access_token` em memória.
3. Consultar/atualizar `GET/PATCH /empresa`; gerir ginásios e planos usando o token administrativo.
4. Enviar `X-Admin-Token` nas rotas de empresa, ginásios, planos, clientes, histórico e marcação manual de presença.
5. Tratar `401` descartando o token e solicitando login novamente. Rotas administrativas de outra empresa respondem como não encontradas.
6. Para marcar uma presença manualmente, chamar `POST /presencas/marcar`; a sessão determina a empresa e o servidor confirma que o ginásio pertence a ela.

Não há refresh token, logout remoto, paginação ou filtros de listagem. O token expira em uma hora. `scripts/criar_admin.py` também permite provisionar localmente uma empresa, seu administrador e o primeiro ginásio; se houver registros anteriores migrados, o script também pode adicionar um administrador à empresa `Empresa migrada`.

## Erros e códigos HTTP

Formato geral:

```json
{ "detail": "Email já registado" }
```

- `200`: leitura ou atualização concluída.
- `201`: ginásio, plano ou cliente criado.
- `401`: login inválido ou token admin ausente/inválido/expirado.
- `403`: regra de acesso ao cliente/plano/presença negou a operação.
- `404`: ginásio, plano ou cliente não encontrado.
- `409`: email, credencial ou registro duplicado.
- `422`: validação do corpo/datas falhou; `detail` pode ser array de erros Pydantic.
- `503`: SQLite indisponível, schema incompleto ou segredo de sessão ausente.

Erros de rede/CORS não retornam JSON de aplicação; confira `FRONTEND_ORIGINS`, protocolo, host e porta configurados.

## Regras de negócio de presença

- Cliente e plano precisam estar ativos e a assinatura vigente.
- O plano pode restringir ginásios, dias, horário, duração e visitas semanais/mensais.
- A semana começa na segunda-feira; o mês é calendário.
- Não pode haver duas entradas abertas do mesmo cliente, inclusive em pedidos concorrentes.
- A saída fecha a presença e devolve a duração da sessão.
- `GET /presencas` contém dados pessoais e exige token admin.

## Testes

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

A suíte usa SQLite em memória e cobre health, login, autorização, cadastro, duplicidade, assinatura e ciclo de presença. Não altera `gym_presence.db`.

## Backup e restauração

Crie backup consistente sem interromper a API:

```powershell
python scripts/backup_sqlite.py
```

Os backups ficam em `%LOCALAPPDATA%\GymPresence\backups` e passam por `PRAGMA integrity_check`. Proteja-os como dados pessoais e defina retenção.

Para restaurar: pare a API; preserve o banco atual se necessário; copie o arquivo de backup para `%LOCALAPPDATA%\GymPresence\gym_presence.db`; reinicie a API e verifique `/health/ready`. Não apague o banco para zerar dados sem antes fazer backup.

## Segurança e limitações

- `.env` contém o segredo HMAC e nunca deve ser versionado ou enviado ao frontend.
- Use `X-Admin-Token` somente em HTTPS fora do desenvolvimento local; token em memória reduz exposição a XSS comparado a `localStorage`.
- CORS permite apenas `FRONTEND_ORIGINS`; não use wildcard. Atualize essa variável para a origem do frontend implantado.
- O backend não limita tentativas de login; se houver exposição de rede, use um proxy/firewall com rate limit.
- O cadastro público não valida email nem limita tentativas. Não exponha o endpoint de cadastro à internet em produção sem adicionar verificação, rate limiting e proteção contra abuso.
- SQLite é local e single-server, sem failover/backup gerenciado. Para operação multi-instância, faça uma migração arquitetural para banco servidor.
- Não use PIN simples nem armazene imagens ou templates biométricos reais neste protótipo.
- O projeto Supabase criado anteriormente não está conectado nem é apagado por esta configuração SQLite. Confira a conta Supabase separadamente se quiser removê-lo.
