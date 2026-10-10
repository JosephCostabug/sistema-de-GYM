# Gym Presence API

Backend REST para gerir ginásios, planos, clientes e presenças. A aplicação não serve uma interface web; a documentação interativa da API fica disponível no Swagger UI do FastAPI.

## Requisitos

- Python 3.10 ou superior
- `pip`
- PostgreSQL 16 ou superior
- Docker Compose (opcional, para executar PostgreSQL em contentor)

Use somente `.venv` como ambiente virtual do projeto. `.venv-1` e `.venv-2` foram removidos. Os três padrões ficam ignorados no `.gitignore` para impedir que ambientes locais sejam versionados.

## Instalação e execução

Na raiz do projeto, crie e ative apenas o ambiente `.venv`.

```bash
py -3 -m venv .venv
```

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Bash:

```bash
source .venv/Scripts/activate
```

Ative o ambiente virtual e instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Para desenvolvimento local, copie `.env.example` para `.env`. Sem `DATABASE_URL`, o modo `development` usa o SQLite persistente `gym_presence.db`.

Suba o PostgreSQL local:

```bash
docker compose up -d postgres
```

O Compose é apenas para desenvolvimento local: cria a base `gym_presence` com credenciais de demonstração e persiste os dados no volume `postgres_data`. Não reutilize essa senha em produção.

Se já tiver PostgreSQL instalado no Windows, crie o utilizador e a base para a aplicação. Este comando solicita a senha administrativa local do PostgreSQL no terminal; digite-a diretamente no prompt e não a partilhe.

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -W -U postgres -h 127.0.0.1 -d postgres -f scripts/init_postgres.sql
```

Para usar o PostgreSQL de desenvolvimento do Compose, configure a URL abaixo:

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://gym_presence_app:gym_dev_password@localhost:5432/gym_presence"
```

Bash:

```bash
export DATABASE_URL="postgresql+psycopg://gym_presence_app:gym_dev_password@localhost:5432/gym_presence"
```

Em `.env`, use `APP_ENV=development` e informe a URL desejada. Nunca versione `.env`.

Crie a conta administrativa inicial. O comando pede o email e a senha sem mostrá-la; no desenvolvimento, gera um segredo local de sessão em `.env` se necessário.

```bash
python scripts/criar_admin.py
```

O bootstrap inicial recusa criar outra conta se já existir um administrador. Senhas têm pelo menos 12 caracteres em desenvolvimento e 16 em produção; a base guarda somente um hash `scrypt`.

Inicie a API:

```bash
uvicorn app.main:app --reload
```

Em desenvolvimento, o primeiro arranque cria as tabelas e dados de demonstração. Em produção, não cria schema nem carrega dados falsos: aplique as migrations antes de iniciar.

`scripts/init_postgres.sql` configura uma credencial fixa apenas para desenvolvimento local. Em produção, gere outra senha e forneça a URL através de um gestor de segredos. O utilizador da aplicação tem acesso de proprietário somente à base `gym_presence`; não use a conta `postgres` na API.

Por omissão, o servidor fica em `http://127.0.0.1:8000`. A documentação interativa fica em `/docs` e o esquema OpenAPI em `/openapi.json`.

## Autenticação administrativa

Obtenha um token através de `POST /admin/login` com a conta criada. O token assinado expira após uma hora. Envie-o no cabeçalho `X-Admin-Token` para endpoints administrativos. Em produção, `ADMIN_TOKEN_SECRET` precisa ter pelo menos 32 bytes e vir do gestor de segredos.

Exemplo de login:

```bash
curl -X POST http://127.0.0.1:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@gym.local","password":"use-a-sua-senha-forte"}'
```

Use HTTPS e um gestor de segredos. Não inclua senha ou token em scripts versionados/logs. A senha literal `admin` não é aceita: é trivial e não é segura para produção. Para rotação operacional, use `python scripts/alterar_senha_admin.py` no ambiente ligado à base.

## Endpoints

| Método | Caminho | Acesso | Descrição |
| --- | --- | --- | --- |
| `POST` | `/admin/login` | Público | Autentica uma conta admin e devolve token expirável. |
| `POST` | `/ginasios` | Administrador | Regista ginásio para iniciar uma base de produção vazia. |
| `GET` | `/ginasios` | Público | Lista os ginásios disponíveis. |
| `GET` | `/planos` | Público | Lista os planos. |
| `GET` | `/planos/{plano_id}` | Público | Consulta um plano. |
| `POST` | `/planos` | Administrador | Cria um plano. |
| `PUT` | `/planos/{plano_id}` | Administrador | Substitui as regras de um plano. |
| `GET` | `/clientes` | Administrador | Lista clientes. |
| `GET` | `/clientes/{cliente_id}` | Administrador | Consulta cliente, plano e utilização. |
| `POST` | `/clientes` | Administrador | Regista um cliente no ginásio. |
| `PATCH` | `/clientes/{cliente_id}/assinatura` | Administrador | Altera plano e/ou datas da assinatura do cliente. |
| `POST` | `/presencas/marcar` | Público | Regista entrada ou saída por credencial. |
| `GET` | `/presencas` | Administrador | Lista o histórico de presenças. |
| `GET` | `/health/live` | Público | Liveness para orquestrador. |
| `GET` | `/health/ready` | Público | Verifica conexão e prontidão do banco. |

### Registar cliente

```bash
curl -X POST http://127.0.0.1:8000/clientes \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_ACCESS_TOKEN" \
  -d '{
    "nome": "Ana Costa",
    "email": "ana@example.com",
    "telefone": "910000000",
    "plano_id": "plano-basico",
    "assinatura_inicio": "2026-10-09T00:00:00",
    "assinatura_fim": "2026-11-09T23:59:59",
    "credenciais": [{"metodo": "cartao", "codigo": "CARD-ANA-001"}]
  }'
```

O email é normalizado para minúsculas. Emails e credenciais já associados a outro cliente são rejeitados. `plano_id` tem de existir e o início da assinatura tem de anteceder o fim.

### Personalizar plano

`PUT /planos/{plano_id}` recebe a representação completa do plano. Campos não fornecidos voltam aos valores predefinidos do schema.

```json
{
  "nome": "Acesso personalizado",
  "descricao": "Até cinco visitas semanais, de segunda a sábado",
  "max_visitas_semana": 5,
  "max_visitas_mes": 20,
  "hora_inicio": "06:00:00",
  "hora_fim": "22:00:00",
  "dias_semana": [0, 1, 2, 3, 4, 5],
  "duracao_maxima_minutos": 120,
  "ginasios_permitidos": ["gym-centro", "gym-norte"],
  "ativo": true
}
```

`max_visitas_semana` e `max_visitas_mes` podem ser `null` para não impor limites. `hora_inicio` e `hora_fim` também podem ser `null`. Os dias usam `0` para segunda-feira até `6` para domingo.

### Personalizar assinatura de cliente

Envie apenas os campos que pretende alterar para `PATCH /clientes/{cliente_id}/assinatura`:

```json
{
  "plano_id": "plano-premium",
  "assinatura_inicio": "2026-10-09T00:00:00",
  "assinatura_fim": "2027-10-08T23:59:59"
}
```

## Códigos de resposta

- `201`: cliente registado.
- `200`: restantes operações concluídas.
- `401`: token administrativo ausente ou inválido.
- `404`: cliente ou plano não encontrado.
- `409`: email ou credencial já registados.
- `422`: corpo inválido ou datas inconsistentes.
- `503`: configuração ou banco indisponível.

## Banco de dados

O SQLAlchemy conecta ao PostgreSQL pela variável `DATABASE_URL`, usando o driver Psycopg 3. O schema contém `ginasios`, `planos`, `clientes`, `credenciais`, `presencas` e `contas_admin`; email e pares método/código de credencial têm restrições de unicidade. Senhas administrativas são guardadas como hash `scrypt`. Criação de clientes, alterações de plano/assinatura e marcações de presença são persistidas em transações.

Alembic controla o schema. Em produção, o servidor recusa iniciar se as migrations estiverem ausentes; em desenvolvimento, `create_all` cria o schema e os registros de demonstração.

## Deploy de produção

1. Criar um projeto Supabase (ou outro PostgreSQL gerido), definir senha do banco e guardar as credenciais no gestor de segredos. No Supabase, obter a URI em `Project Settings > Database`; usar a URI PostgreSQL do banco, não as chaves `anon` ou `service_role` da API.
2. No Supabase, copiar a URI exata de `Connect > Session pooler` e executar `python scripts/configurar_supabase.py`; a senha é lida sem eco e a URI fica apenas em `.env`. Em deploy, configure `APP_ENV=production`, `DATABASE_URL` com `sslmode=require` (ou validação mais forte) e `ADMIN_TOKEN_SECRET` com pelo menos 32 bytes no gestor de segredos. SQLite e o Compose de desenvolvimento são recusados no modo produção.
3. Instalar `requirements.txt` e aplicar `python -m alembic upgrade head` antes de iniciar a API.
4. Criar a primeira conta admin com `python scripts/criar_admin.py`; em produção é obrigatório email real e senha com pelo menos 16 caracteres.
5. Iniciar a API atrás de proxy HTTPS, firewall e processo supervisionado, por exemplo `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`. Swagger/OpenAPI fica desativado no modo produção.
6. Criar ginásios com `POST /ginasios` e planos com `POST /planos`; o modo produção não insere clientes, credenciais ou dados de demonstração.
7. Configurar monitoramento de `/health/live` e `/health/ready`, retenção de logs, alarmes, backup e teste de restauração, limitação de tentativas de login no proxy/WAF e políticas de proteção de dados.

Ao copiar a URI padrão do Supabase (`postgresql://`), a aplicação converte-a para Psycopg 3. Para o pooler transacional Supabase, desativa prepared statements automaticamente.

Ainda é necessário criar/autenticar o projeto Supabase, colocar a URI e os segredos no ambiente local/deploy e testar essa conexão real. Certificado TLS/proxy, backup e restauração, rate limit distribuído no proxy/WAF, observabilidade e requisitos legais para dados biométricos também dependem do ambiente de destino.

Depois de confirmar que nenhum cliente usa chaves antigas, desative a chave legada `service_role` em `Project Settings > API Keys`; a API deste projeto conecta diretamente ao PostgreSQL e não precisa de API key Supabase. Nunca use a chave `service_role` no `.env` desta aplicação.

Para parar o PostgreSQL sem apagar dados:

```bash
docker compose down
```

Não use `docker compose down -v` a menos que queira apagar o volume e todos os dados locais.

Os clientes e credenciais de demonstração existem apenas em `development`. Não utilize PINs simples nem dados biométricos reais no protótipo; em produção, guarde referências seguras e aplique políticas de retenção e proteção de dados.