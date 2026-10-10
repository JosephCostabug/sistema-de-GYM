# Gym Presence API

Backend REST para gerir ginásios, planos, clientes, assinaturas e presenças. O projeto usa FastAPI, SQLAlchemy e **SQLite local**. Não inclui interface própria; a documentação interativa fica no Swagger.

## 1. O que esta aplicação faz

- Mantém ginásios e planos com regras de acesso.
- Regista clientes, assinaturas e credenciais de acesso.
- Autoriza entradas com base em estado, período, horário, dias, ginásios e limites de visitas.
- Regista entrada e saída e expõe o histórico para administradores.
- Autentica administradores com senha `scrypt` e token HMAC com validade de uma hora.
- Guarda os dados num arquivo SQLite persistente e permite gerar backups consistentes.

## 2. Limites importantes

SQLite é apropriado para desenvolvimento e uma instalação pequena num único servidor. O arquivo não deve ser compartilhado por várias instâncias da API, armazenado em pasta de rede ou sincronizado pelo OneDrive enquanto há escrita. Para alta concorrência, múltiplos servidores, failover ou alta disponibilidade, será necessário migrar para um banco servidor e reavaliar a arquitetura.

O projeto Supabase criado durante a configuração anterior **não é usado pela aplicação**. O workspace não o apaga. Confira o painel e remova esse projeto se não quiser mantê-lo; confirme antes se há cobrança ou dados que queira preservar.

## 3. Requisitos e estrutura

- Python 3.10 ou superior
- `pip`
- Windows, macOS ou Linux

Use somente `.venv` como ambiente virtual. A estrutura principal é:

```text
app/
  data/       modelos SQLAlchemy, caminho local e repositório
  models/     schemas e validação Pydantic
  routes/     endpoints HTTP
  services/   regras de acesso e autenticação
scripts/      configuração SQLite, admin e backup
 tests/       testes HTTP com SQLite em memória
```

## 4. Instalação no Windows

Na raiz do projeto, crie/ative o ambiente virtual e instale as dependências:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Para desenvolvimento/testes:

```powershell
python -m pip install -r requirements-dev.txt
```

Se estiver usando um `.env` antigo com PostgreSQL/Supabase, mude a configuração sem mostrar nem apagar o segredo de sessão admin:

```powershell
python scripts/configurar_sqlite.py
```

O configurador seleciona `APP_ENV=development`, remove `DATABASE_URL` e a referência Supabase do `.env`, preserva `ADMIN_TOKEN_SECRET` e copia a base antiga do projeto para o caminho local se ainda não houver uma cópia lá.

Na migração deste workspace, a base ativa foi copiada para LocalAppData com a API nativa de backup do SQLite e validada. O antigo `gym_presence.db` na raiz do workspace foi mantido intacto como cópia de recuperação; a aplicação não o usa mais. Depois de confirmar que a nova localização e os backups estão corretos, essa cópia antiga pode ser removida manualmente.

## 5. Banco e arquivos locais

No Windows, o banco ativo fica em:

```text
%LOCALAPPDATA%\GymPresence\gym_presence.db
```

No macOS/Linux, fica em:

```text
~/.local/share/gym-presence/gym_presence.db
```

Esse local fica fora do workspace sincronizado. O banco contém as tabelas `ginasios`, `planos`, `clientes`, `credenciais`, `presencas` e `contas_admin`. Chaves estrangeiras estão ativas, emails e credenciais têm restrições de unicidade, e um índice parcial impede mais de uma presença aberta por cliente.

`DATABASE_URL` pode apontar para outro arquivo SQLite, se necessário. Caminhos relativos são resolvidos a partir da raiz do projeto. URLs PostgreSQL/Supabase são recusadas por esta configuração SQLite.

O arquivo `.env` guarda `ADMIN_TOKEN_SECRET` e outras configurações locais; ele está ignorado no `.gitignore`. Nunca o inclua em commits, capturas de tela, logs ou mensagens. O arquivo `.env.example` é um modelo, não deve conter segredos reais.

Em `development`, o primeiro arranque cria tabelas e dados de demonstração se a base estiver vazia. Em `test`, cria o schema sem seed. O seed não sobrescreve registros existentes.

## 6. Conta administrativa

Crie a primeira conta uma vez:

```powershell
python scripts/criar_admin.py
```

O email padrão local é `admin@gym.local`. A senha é lida sem eco, precisa ter pelo menos 12 caracteres e é armazenada somente como hash `scrypt`. O segredo HMAC dos tokens é criado em `.env` se ainda não existir. O script bloqueia um segundo bootstrap.

A senha `admin` não é aceita: é trivial. Para mudar a senha de uma conta existente:

```powershell
python scripts/alterar_senha_admin.py
```

Esse comando também lê a senha sem eco. Digite senhas somente nos prompts locais; nunca as envie no chat.

### Login

`POST /admin/login` recebe:

```json
{
  "email": "admin@gym.local",
  "password": "a-sua-senha-local"
}
```

Resposta:

```json
{
  "access_token": "<token-assinado>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Envie o token de `access_token` no cabeçalho `X-Admin-Token` das rotas marcadas como Admin. O token expira em uma hora. Senha errada, token ausente, inválido ou expirado retorna `401`.

## 7. Executar e verificar

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- Health do processo: `http://127.0.0.1:8000/health/live`
- Health do banco: `http://127.0.0.1:8000/health/ready`

Interrompa o servidor no terminal com `Ctrl+C`.

## 8. Endpoints

| Método | Caminho | Acesso | Descrição |
| --- | --- | --- | --- |
| `GET` | `/health/live` | Público | Confirma que o processo HTTP está ativo. |
| `GET` | `/health/ready` | Público | Confirma conexão SQLite e existência das tabelas. |
| `POST` | `/admin/login` | Público | Autentica a conta admin e emite token. |
| `GET` | `/ginasios` | Público | Lista ginásios. |
| `POST` | `/ginasios` | Admin | Cria ginásio. |
| `GET` | `/planos` | Público | Lista planos. |
| `GET` | `/planos/{plano_id}` | Público | Consulta plano. |
| `POST` | `/planos` | Admin | Cria plano. |
| `PUT` | `/planos/{plano_id}` | Admin | Substitui as regras do plano. |
| `GET` | `/clientes` | Admin | Lista clientes. |
| `GET` | `/clientes/{cliente_id}` | Admin | Consulta cliente, plano e uso. |
| `POST` | `/clientes` | Admin | Regista cliente e credenciais. |
| `PATCH` | `/clientes/{cliente_id}/assinatura` | Admin | Altera plano e/ou datas. |
| `POST` | `/presencas/marcar` | Público | Marca entrada ou saída por credencial. |
| `GET` | `/presencas` | Admin | Lista histórico de presenças. |

### Criar plano

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

`dias_semana`: `0` = segunda-feira até `6` = domingo. Limites e horários aceitam `null`; `ginasios_permitidos: []` significa sem restrição de ginásio. `PUT` substitui a representação completa do plano.

### Registar cliente

```json
{
  "nome": "Ana Costa",
  "email": "ana@example.com",
  "telefone": "910000000",
  "plano_id": "plano-basico",
  "assinatura_inicio": "2026-10-10T00:00:00+00:00",
  "assinatura_fim": "2026-11-10T00:00:00+00:00",
  "credenciais": [{"metodo": "cartao", "codigo": "CARD-ANA-001"}]
}
```

Email é normalizado para minúsculas. Plano deve existir; email e par método/código da credencial são únicos. Datas precisam usar o mesmo padrão de fuso e o início precisa anteceder o fim.

### Personalizar assinatura

`PATCH /clientes/{cliente_id}/assinatura` aceita apenas os campos que mudam:

```json
{
  "plano_id": "plano-premium",
  "assinatura_fim": "2027-10-10T00:00:00+00:00"
}
```

### Marcar presença

```json
{
  "ginasio_id": "gym-centro",
  "metodo": "cartao",
  "credencial": "CARD-ANA-001",
  "tipo": "entrada"
}
```

Métodos aceitos: `biometria`, `face`, `cartao`, `pin`, `qr`. `tipo` aceita `entrada`, `saida` ou pode ser omitido para alternar conforme exista uma presença aberta.

## 9. Regras de acesso

Uma entrada só é permitida se cliente e plano estiverem ativos, a assinatura estiver vigente, o ginásio/dia/horário forem permitidos, não houver outra entrada aberta e os limites de visita não tiverem sido atingidos. Sem limites semanais/mensais (`null`), não há restrição correspondente.

A semana de contagem começa na segunda-feira e o mês é de calendário. A saída fecha a presença aberta e devolve duração e eventual aviso de tempo acima do plano. Uma sessão não pode ser aberta duas vezes para o mesmo cliente, inclusive em pedidos concorrentes.

## 10. Códigos HTTP

- `200`: operação concluída.
- `201`: ginásio, plano ou cliente criado.
- `401`: credenciais admin ou token inválidos/ausentes/expirados.
- `403`: acesso negado por regra de cliente/plano/presença.
- `404`: cliente, plano ou ginásio não encontrado.
- `409`: email, credencial ou registro duplicado.
- `422`: conteúdo inválido ou datas inconsistentes.
- `503`: SQLite ou schema indisponível.

## 11. Testes

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Os testes usam SQLite em memória e cobrem health checks, login, proteção admin, cadastro, duplicidade, alteração parcial de assinatura e ciclo de presença. Não modificam a base local real.

## 12. Backup e restauração

Crie backup consistente sem parar a API:

```powershell
python scripts/backup_sqlite.py
```

O arquivo é salvo em `%LOCALAPPDATA%\GymPresence\backups` e passa por `PRAGMA integrity_check`. Backups contêm dados pessoais e referências de credenciais: proteja o diretório e mantenha retenção limitada.

Para restaurar um backup:

1. Pare a API com `Ctrl+C`.
2. Faça uma cópia do banco atual para uma pasta segura, se precisar preservá-lo.
3. Copie o arquivo escolhido de `%LOCALAPPDATA%\GymPresence\backups` para `%LOCALAPPDATA%\GymPresence\gym_presence.db`.
4. Reinicie a API e confirme `/health/ready`.

Não apague o banco para “reiniciar” o sistema: isso remove clientes, administradores, planos e histórico.

## 13. Segurança e operação

- Esta configuração SQLite é local/single-server; não exponha diretamente à internet nem execute várias instâncias escrevendo no mesmo arquivo.
- Use senha admin forte, mantenha `.env` privado e faça backups protegidos.
- O token admin não tem rate limit embutido; se a API for exposta numa rede, use proxy autenticado/firewall e limite de tentativas.
- Os clientes e credenciais de demonstração só são inseridos em `development` numa base vazia.
- Não use PIN simples nem dados biométricos reais neste protótipo. Armazene referências de credencial, não imagens, templates biométricos ou segredos em claro.
- A API não se conecta ao projeto Supabase anterior. O vínculo local e a URL remota foram removidos do `.env`; o projeto remoto na conta Supabase não é apagado automaticamente.
