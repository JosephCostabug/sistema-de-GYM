# Fluxo completo do Gym Presence

Este documento descreve como o frontend, a API e o banco de dados trabalham juntos no fluxo multiempresa atual. É uma referência funcional para desenvolvimento e manutenção; os contratos HTTP e as regras executáveis continuam definidos pelo código da aplicação.

## 1. Visão geral da arquitetura

```text
Navegador
  └─ frontend/ (HTML, CSS e JavaScript ES modules)
       └─ fetch JSON + X-Admin-Token
            └─ app/main.py (FastAPI, CORS e routers)
                 ├─ app/routes/       validação HTTP e autorização
                 ├─ app/services/     autenticação e regras de acesso
                 └─ app/data/         operações transacionais, migrações e SQLAlchemy
                      └─ SQLite local
```

- **Frontend:** páginas estáticas servidas por HTTP. `frontend/js/api.js` centraliza a URL da API, o envio opcional do token e o tratamento de erros HTTP.
- **API:** FastAPI valida os corpos JSON com schemas Pydantic, chama os serviços e aplica autenticação nas rotas administrativas.
- **Persistência:** SQLAlchemy acessa SQLite. O repositório em `app/data/store.py` concentra as consultas e transações.
- **Separação entre empresas:** cada administrador pertence a uma empresa. As rotas usam a empresa resolvida pelo token para consultar e gravar dados. O navegador não escolhe nem envia um `empresa_id` de confiança.

A empresa é um **tenant lógico** dentro do mesmo banco SQLite. Isto separa os dados na aplicação, mas não equivale a bancos fisicamente separados nem torna o protótipo pronto para múltiplas instâncias de produção.

## 2. Modelo de dados e relações

```text
Empresa
 ├─ Administradores
 ├─ Ginásios
 ├─ Planos
 │    └─ ginasios_permitidos: IDs dos ginásios elegíveis
 ├─ Clientes
 │    ├─ plano_id → Plano
 │    └─ Credenciais
 └─ Presenças
      ├─ cliente_id → Cliente
      └─ ginasio_id → Ginásio
```

- Uma empresa pode ter vários administradores, ginásios, planos, clientes e presenças.
- O email da conta administrativa é único em toda a instalação. Emails de clientes e credenciais são únicos dentro de cada empresa.
- O cliente aponta para um plano; **não possui um `ginasio_id` direto**. O ginásio associado ao cliente é definido indiretamente pelos ginásios permitidos pelo plano.
- Um plano precisa permitir um ou mais ginásios pertencentes à mesma empresa.
- A marcação de presença guarda o ginásio efetivamente usado.

## 3. Preparação e inicialização local

Use um terminal na raiz do projeto. Os comandos abaixo seguem a configuração local documentada em `README.md`:

```powershell
.\.venv\Scripts\python.exe scripts\configurar_sqlite.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

Em outro terminal, inicie o frontend:

```powershell
.\.venv\Scripts\python.exe -m http.server 5500 --directory frontend
```

Abra `http://127.0.0.1:5500`. A API fica em `http://127.0.0.1:8000`; sua documentação interativa está em `/docs`.

Ao iniciar, o lifespan da aplicação chama `store.inicializar()`: as tabelas são criadas e a migração de tenant associa registros legados a uma empresa. O banco local padrão fica em `%LOCALAPPDATA%\GymPresence\gym_presence.db` no Windows ou `~/.local/share/gym-presence/gym_presence.db` em macOS/Linux. `DATABASE_URL` pode substituir o caminho, mas o projeto aceita somente SQLite.

`configurar_sqlite.py` configura o `.env` local e cria `ADMIN_TOKEN_SECRET` se ainda não houver um valor. Esse segredo assina os tokens de sessão; não o publique, não o coloque no frontend e não o compartilhe.

## 4. Primeiro cadastro: empresa, administrador e ginásio inicial

### Pela interface

1. Abra `signup.html` (linkado a partir de `index.html`).
2. Informe os dados da empresa, o email e a palavra-passe do administrador, e os dados do primeiro ginásio.
3. O JavaScript envia um único `POST /admin/register`.
4. O backend valida os schemas, gera IDs, gera um hash scrypt da palavra-passe e cria empresa, administrador e ginásio numa única transação.
5. Se o email administrativo já estiver em uso, ou se a transação falhar, não fica um cadastro parcial.
6. Após o sucesso, a interface informa que a conta foi criada. Entre em `login.html` com o email e a palavra-passe escolhidos.

O endpoint devolve um token junto com os dados recém-criados, mas a página de cadastro não persiste esse token entre páginas. O login seguinte emite uma nova sessão.

### Contrato de cadastro

```http
POST /admin/register
Content-Type: application/json
```

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

Sucesso: `201 Created`, com `empresa`, `ginasio`, `access_token`, `token_type` e `expires_in`. A senha em claro não é devolvida nem armazenada.

## 5. Login e contexto de empresa

O formulário de `login.html` chama:

```http
POST /admin/login
Content-Type: application/json
```

```json
{
  "email": "admin@example.com",
  "password": "uma-palavra-passe-forte"
}
```

Com credenciais válidas, a API devolve um token assinado com validade de uma hora. Para cada operação administrativa:

```http
X-Admin-Token: <access_token>
```

O token identifica o administrador; em cada pedido protegido, o backend valida assinatura e expiração, carrega a conta e obtém o `empresa_id` confiável dessa conta. O ID não é aceito do navegador como substituto dessa validação. O frontend mantém o token em memória; ao terminar a sessão ou receber `401`, solicita novo login.

## 6. Perfil, ginásios e planos

Depois do login, `login.html` carrega o perfil da empresa, seus ginásios e seus planos. O painel permite editar o perfil, adicionar unidades e criar planos.

| Ação | Endpoint | Regra principal |
| --- | --- | --- |
| Ler perfil | `GET /empresa` | Retorna a empresa do token. |
| Atualizar perfil | `PATCH /empresa` | Só atualiza a empresa do token; envie um ou mais campos. |
| Listar ginásios | `GET /ginasios` | Lista somente as unidades da empresa autenticada. |
| Criar ginásio | `POST /ginasios` | Cria a unidade dentro da empresa do token. |
| Listar planos | `GET /planos` | Lista somente os planos da empresa autenticada. |
| Consultar plano | `GET /planos/{plano_id}` | Um plano de outra empresa aparece como não encontrado. |
| Criar plano | `POST /planos` | Exige um ou mais ginásios da empresa autenticada. |
| Substituir plano | `PUT /planos/{plano_id}` | Atualiza um plano próprio e valida novamente seus ginásios. |

Ginásio:

```json
{
  "nome": "Unidade Norte",
  "endereco": "Rua do Estádio, 12"
}
```

Plano:

```json
{
  "nome": "Plano Base",
  "descricao": "Acesso durante a semana",
  "max_visitas_semana": 3,
  "max_visitas_mes": 12,
  "dias_semana": [0, 1, 2, 3, 4, 5],
  "ginasios_permitidos": ["<id-de-ginasio-da-empresa>"],
  "ativo": true
}
```

Os IDs são gerados pelo backend. Um plano que referencia um ginásio de outra empresa ou que não referencia nenhuma unidade é rejeitado.

## 7. Cadastro e consulta de clientes

1. Abra `clientes.html` e autentique-se.
2. A página busca, com o token, os ginásios e os planos da empresa.
3. Ao escolher um ginásio, o frontend oferece apenas planos ativos que permitam aquela unidade.
4. Informe nome, email, período da assinatura e a credencial do cliente.
5. O frontend envia `POST /clientes` com `X-Admin-Token`.
6. O backend verifica que o plano existe no tenant, está ativo e está associado a pelo menos um ginásio; valida os dados, verifica duplicados e grava cliente e credenciais na transação.
7. A listagem exibida após o cadastro contém apenas clientes da empresa autenticada.

Exemplo de corpo:

```json
{
  "nome": "Ana Costa",
  "email": "ana@example.com",
  "telefone": "910000000",
  "plano_id": "<id-de-plano-da-empresa>",
  "assinatura_inicio": "2026-10-10T00:00:00Z",
  "assinatura_fim": "2026-11-10T00:00:00Z",
  "credenciais": [
    { "metodo": "cartao", "codigo": "CARD-ANA-001" }
  ]
}
```

Rotas administrativas relacionadas:

- `GET /clientes`: lista clientes do tenant.
- `POST /clientes`: cria um cliente e suas credenciais.
- `GET /clientes/{cliente_id}`: devolve o cliente, seu plano e o uso do plano; um ID de outro tenant retorna `404`.
- `PATCH /clientes/{cliente_id}/assinatura`: altera plano ou datas da assinatura, validando o estado final.

O cadastro exige que cliente e plano estejam associados ao tenant autenticado. Email e credenciais podem repetir em empresas distintas, mas não dentro da mesma empresa. A interface coleta uma credencial por cliente; a API aceita uma lista.

## 8. Marcação manual de entrada e saída

A marcação manual exige uma sessão administrativa. O tenant vem da sessão; o ginásio enviado no pedido é validado dentro desse tenant:

```http
POST /presencas/marcar
Content-Type: application/json
X-Admin-Token: <token-da-sessao>
```

```json
{
  "ginasio_id": "<id-do-ginasio>",
  "metodo": "cartao",
  "credencial": "CARD-ANA-001",
  "tipo": "entrada"
}
```

1. A API resolve o administrador e a empresa a partir do token.
2. Confirma que o ginásio pertence à empresa autenticada; um ID de outra empresa responde `404`.
3. Procura a credencial somente entre clientes dessa empresa.
4. Carrega o plano do cliente dentro do mesmo tenant.
5. Valida cliente ativo, plano ativo, validade da assinatura, permissão do ginásio, dia, horário, limites de visitas e ausência de outra entrada aberta.
6. Registra a presença. Com `tipo: "saida"`, fecha a entrada aberta; se `tipo` for omitido, alterna entre entrada e saída conforme a presença aberta.

`GET /presencas` exige token e lista somente o histórico da empresa do administrador. Uma marcação recusada retorna `403` com `detail` explicando a regra que bloqueou o acesso. Uma credencial de outra empresa não é encontrada pelo terminal.

A autenticação de dispositivos e o gateway de eventos assinados pertencem à Fase 2 e ainda não estão implementados.

## 9. Isolamento, migração e setup administrativo local

- O escopo por tenant é aplicado no servidor e nas consultas do repositório; não depende do frontend filtrar dados.
- A migração SQLite adiciona as chaves de empresa e associa os registros de instalações anteriores a `Empresa migrada`, preservando seus dados.
- Para adicionar administradores localmente ou provisionar uma empresa fora da interface, use `scripts/criar_admin.py`. Se houver uma empresa legada, o script oferece associar o novo administrador a ela.
- Para alterar a palavra-passe de uma conta existente, use `scripts/alterar_senha_admin.py`.
- Se o email administrativo já existir, o cadastro público não cria outra conta com esse endereço.

### Primeiro corte da arquitetura-alvo

`app/data/control_plane.py`, `app/data/tenant_databases.py` e `app/services/provisionamento.py` implementam, em paralelo ao protótipo, um plano de controlo SQLite e provisionamento repetível de bases SQLite isoladas. O plano central guarda empresa, email administrativo globalmente único e estado/localização da base.

O schema tenant versão 2 inclui ginásio único, membros da equipa, planos, clientes, assinaturas, credenciais, presenças e auditoria. As FKs e restrições locais garantem que cliente e assinatura/plano pertencem à mesma base, email e credenciais são únicos por tenant e cada cliente referencia a sua própria assinatura. Triggers impedem remover/desativar o último administrador ativo, apagar presenças, alterar os seus dados originais ou editar/eliminar auditoria; uma presença pode ser anulada uma vez, com autor e justificação. A auditoria aceita apenas metadados redigidos, nunca dados pessoais ou segredos em claro.

`tests/test_provisioning.py` valida o schema e esses invariantes, além do isolamento entre arquivos, repetição e recuperação de falha. O caminho continua fora das rotas e não altera a base existente. Não há migração automática: bases com versão ou tabelas inesperadas são recusadas. Isto ainda não é a implementação completa da arquitetura-alvo nem está pronto para produção/PostgreSQL.

## 10. Erros e comportamento do frontend

O frontend lê a resposta JSON da API e mostra `detail`; erros de validação `422` mostram as mensagens dos campos. Códigos relevantes:

| Código | Significado típico |
| --- | --- |
| `201` | Empresa, ginásio, plano ou cliente criado. |
| `400` | Plano inválido ou referência a ginásio não pertencente à empresa. |
| `401` | Login inválido, token ausente, expirado ou inválido. |
| `403` | Marcação recusada pelas regras de acesso. |
| `404` | Recurso não encontrado no tenant autenticado. |
| `409` | Email de administrador duplicado, cliente duplicado ou credencial em uso no tenant. |
| `422` | Corpo, email, credencial, horário ou datas inválidos. |
| `503` | Segredo administrativo ausente ou indisponibilidade/configuração do banco. |

Erros de rede e CORS não são respostas JSON da API. Para o frontend local, confira se API e servidor estático estão ativos e se a origem está na allowlist `FRONTEND_ORIGINS`.

## 11. Limites operacionais e próximos passos antes de produção

- O cadastro de empresa é público e não inclui verificação de email, CAPTCHA ou rate limiting; proteja-o antes de expor à internet.
- O login não tem limitação de tentativas. A implantação pública deve adicionar proteção contra força bruta.
- O token dura uma hora; não há refresh token nem logout remoto.
- Tokens são mantidos em memória nas páginas. Ao navegar para outra página protegida, será necessário autenticar novamente.
- O SQLite configurado neste projeto é local e single-server; o modelo multiempresa atual é lógico, não uma arquitetura multi-instância escalável. Antes de escalar, planeie uma migração para banco servidor e backups apropriados.
- Os dados de cadastro de empresa/admin não fazem confirmação de propriedade do email. Não use dados de demonstração ou credenciais simples com clientes reais.
- Não armazene imagens ou templates biométricos neste protótipo. Métodos como biometria e face representam códigos fornecidos por um leitor externo; não implementam captura biométrica.

## 12. Testes que cobrem o fluxo

Execute na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes da API verificam cadastro, login, gestão de empresa, isolamento entre tenants, referências de ginásio, clientes, credenciais, presença e CORS. Os testes de migração verificam preservação dos registros legados e as restrições de unicidade por empresa.
