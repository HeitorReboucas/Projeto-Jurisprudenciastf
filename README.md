# Coletor de Jurisprudência do STF

Aplicação local para pesquisar documentos públicos no portal oficial de jurisprudência do Supremo Tribunal Federal, baixar inteiros teores em PDF, deduplicar por chave e SHA-256, manter checkpoints em SQLite e, opcionalmente, enviar os arquivos ao Google Drive.

O coletor faz no máximo uma consulta de pesquisa por segundo e não tenta contornar CAPTCHA, bloqueios ou controles de acesso. A integração com o STF usa o endpoint de pesquisa consumido pelo próprio portal; alterações nesse serviço podem exigir atualização de `app/stf.py`.

## Requisitos

- Windows 10/11 (o desenvolvimento também funciona em outros sistemas com Python 3.12+).
- Python 3.12 ou superior.
- Acesso à internet para consultar o STF e baixar documentos.
- Opcional: projeto Google Cloud com Google Drive API habilitada e credenciais OAuth 2.0 do tipo Desktop app.

## Instalação no Windows

No PowerShell, na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Se a política do PowerShell impedir a ativação, use o executável diretamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O workspace do VS Code já está configurado para selecionar `.venv\Scripts\python.exe` automaticamente.

## Google Drive (opcional)

1. No Google Cloud Console, crie ou selecione um projeto e habilite a Google Drive API.
2. Configure a tela de consentimento OAuth e crie um ID de cliente OAuth do tipo **Web application**.
3. Em URIs de redirecionamento autorizados, cadastre `http://localhost:8000/api/drive/oauth/callback`.
4. Baixe o JSON de credenciais para a raiz do projeto com o nome `credentials.json`.
5. Inicie a aplicação localmente na porta 8000 e clique em **Conectar Drive**.
6. Conclua o consentimento no navegador. O token será salvo em `data/google-token.json`, que não é versionado.
7. Selecione uma pasta do seu Drive antes de iniciar a coleta. A aplicação cria dentro dela `STF/{tipo}/{ano}`.

Para configurar outro caminho para o JSON OAuth ou para o token, defina `GOOGLE_CLIENT_SECRETS_FILE` ou `GOOGLE_TOKEN_FILE` no `.env`. O URI de retorno padrão é `http://localhost:8000/api/drive/oauth/callback`.

Sem credenciais do Google, é possível coletar e manter os PDFs localmente em `data/downloads/STF/{tipo}/{ano}`.

## Executar

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abra <http://127.0.0.1:8000>. A documentação interativa da API fica em <http://127.0.0.1:8000/docs> e o schema OpenAPI em <http://127.0.0.1:8000/openapi.json>.

## API

### Criar coleta

`POST /api/jobs` recebe um intervalo inclusivo de publicação, pelo menos um tipo de conteúdo e filtros opcionais:

```json
{
	"content_types": ["acordaos", "informativos"],
	"date_from": "2024-01-01",
	"date_to": "2024-12-31",
	"query": "liberdade de expressão",
	"process_class": "RE",
	"drive_folder_id": null
}
```

Valores aceitos em `content_types`: `acordaos`, `decisoes_monocraticas`, `sumulas` e `informativos`. `drive_folder_id` é opcional; quando informado, requer OAuth concluído. O endpoint retorna `202 Accepted` com o identificador e o estado inicial do job.

### Consultar e retomar

- `GET /api/health`: estado do serviço.
- `GET /api/content-types`: tipos disponíveis.
- `GET /api/jobs`: lista de coletas recentes.
- `GET /api/jobs/{job_id}`: estado, filtros, contadores e item atual.
- `GET /api/jobs/{job_id}/events`: histórico de eventos.
- `POST /api/jobs/{job_id}/resume`: retoma uma execução interrompida ou concluída com erros.
- `GET /api/documents?content_type=acordaos&status=downloaded&limit=100&offset=0`: pesquisa o catálogo local.
- `POST /api/documents/{document_id}/upload` com `{"drive_folder_id":"..."}`: envia novamente um PDF já baixado.
- `GET /api/drive/status`: estado da configuração e autorização do Google Drive.
- `GET /api/drive/auth/url`: inicia o fluxo OAuth.
- `GET /api/drive/folders`: lista pastas disponíveis no Drive.

Erros de validação usam `422`; itens ausentes, `404`; operação não disponível no estado atual, `409`; e falhas no provedor externo, `502` ou um job `completed_with_errors`.

## Persistência e retomada

O banco `data/jurisprudencias.sqlite3` guarda filtros, progresso, checkpoints, metadados, tentativas, erros e eventos. A execução interrompida pode ser retomada pela interface ou por `POST /api/jobs/{job_id}/resume`. A chave do STF evita importar o mesmo registro novamente; o hash SHA-256 identifica PDFs binariamente iguais. Arquivos baixados permanecem no disco quando o upload falha.

Os documentos do STF nem sempre oferecem um arquivo de inteiro teor; esses casos ficam registrados como erro, sem derrubar o restante da coleta. O limite de tamanho por PDF é configurável por `DOWNLOAD_MAX_BYTES` (padrão: 50 MiB).

## Configuração

As opções abaixo podem ser definidas no `.env` ou como variáveis de ambiente:

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `DATA_DIR` | `data` | Diretório do banco, tokens e PDFs. |
| `STF_SEARCH_URL` | endpoint oficial atual | Endpoint JSON de pesquisa do portal STF. |
| `STF_TIMEOUT_SECONDS` | `30` | Timeout da pesquisa. |
| `STF_REQUEST_DELAY_SECONDS` | `1.0` | Pausa mínima entre pesquisas; valores abaixo de 1 são rejeitados. |
| `STF_MAX_ATTEMPTS` | `3` | Tentativas em falhas transitórias. |
| `DOWNLOAD_MAX_BYTES` | `52428800` | Tamanho máximo por PDF. |
| `DOWNLOAD_TIMEOUT_SECONDS` | `60` | Timeout do download. |
| `GOOGLE_CLIENT_SECRETS_FILE` | `credentials.json` | Credenciais OAuth do cliente Desktop app. |
| `GOOGLE_TOKEN_FILE` | `data/google-token.json` | Token OAuth local. |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/drive/oauth/callback` | URI de retorno OAuth. |

O serviço é destinado a uso local confiável; não oferece autenticação de usuário para expor a API publicamente.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes não precisam de credenciais do Google nem fazem chamadas ao STF.