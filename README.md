# Marketplace Search

Aplicação local para pesquisar produtos em diferentes marketplaces e comparar resultados em uma única interface. O projeto utiliza FastAPI e Selenium e oferece uma API HTTP para consultas e integrações.

## Sobre o projeto

Projeto acadêmico de Engenharia de Software da Estácio, unidade Pistão Sul, Distrito Federal.

### Equipe

| Integrante | Matrícula |
|---|---|
| Wesley Gabriel Batista Rosa | 202601418793 |
| Guilherme Araujo | 202408147627 |
| Marcely Bomfim Barella | 202603316301 |
| Fernando Miguel Costa Cardoso | 202601835904 |
| Stenio Daniel Santos de Araújo | 202607148283 |

## Recursos

- Pesquisa em OLX, Mercado Livre, KaBuM, Terabyte, PC Gamer Brasília, AliExpress e Facebook.
- Consultas simultâneas em múltiplas plataformas.
- Interface web com busca, filtros, análise comparativa e exportação de resultados em CSV.
- Identificação de perfis de hardware e variações de termos de pesquisa.
- Indicadores comerciais, incluindo menor preço e mediana dos resultados filtrados.
- Cache para reduzir o tempo de consultas repetidas.
- Endpoints JSON para integração com outras aplicações.

Os resultados dependem da disponibilidade, do conteúdo e das políticas de acesso de cada plataforma. Respeite os termos de uso e as regras aplicáveis ao utilizar o sistema.

## Requisitos

- Python 3.11, 3.12, 3.13 ou 3.14. Python 3.15 ainda não é compatível com as dependências fixadas no projeto.
- Google Chrome para as consultas que utilizam Selenium. O navegador pode ser configurado por variável de ambiente.

## Instalação e execução

Instale as dependências:

```bash
pip install -r requirements.txt
```

Inicie a aplicação:

```bash
python -m marketplace_search
```

Por padrão, a interface é disponibilizada em `http://127.0.0.1:8000`. Para definir o endereço, a porta e impedir a abertura automática do navegador:

```bash
python -m marketplace_search --host 127.0.0.1 --port 8000 --no-browser
```

### Windows

No Windows, a aplicação também pode ser iniciada pelo arquivo `start_marketplace.bat` ou pelo launcher:

```bash
python launcher.py
```

O launcher prepara o ambiente virtual, instala ou atualiza as dependências e inicia a aplicação. Para preparar o ambiente sem iniciar o servidor:

```bash
python launcher.py --bootstrap-only
```

### Instalação como pacote

Também é possível instalar o projeto no ambiente Python ativo e iniciar pelo comando disponibilizado:

```bash
pip install .
marketplace-search
```

## Atualização pelo launcher

O arquivo `start_marketplace.bat` habilita a atualização automática por padrão. Antes de iniciar a aplicação, o launcher pode consultar o repositório configurado e atualizar os arquivos para a branch selecionada.

Comandos disponíveis:

```bash
python launcher.py --auto-update
python launcher.py --update-only
python launcher.py --skip-update
```

Variáveis relacionadas à atualização:

- `MARKETPLACE_AUTO_UPDATE`
- `MARKETPLACE_UPDATE_REPO`
- `MARKETPLACE_UPDATE_BRANCH`
- `MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS`

## Configuração e dados locais

As configurações podem ser definidas por variáveis de ambiente ou em um arquivo `.env` no diretório de execução ou no diretório de dados da aplicação.

Por padrão, os dados de execução ficam fora dos arquivos do projeto:

- Windows: `%LOCALAPPDATA%\MarketplaceSearch`
- Outros sistemas: `~/.marketplace-search`

Nesse diretório, a aplicação armazena artefatos HTML e JSON, perfis persistentes do Selenium e o estado do launcher. Variáveis de configuração comuns:

- `MARKETPLACE_HOME`
- `MARKETPLACE_HOST`
- `MARKETPLACE_PORT`
- `MARKETPLACE_OPEN_BROWSER`
- `MARKETPLACE_FACEBOOK_REGION_SLUG`
- `MARKETPLACE_SAVE_SUCCESS_HTML_SNAPSHOTS`
- `MARKETPLACE_SAVE_SUCCESS_JSON_SNAPSHOTS`
- `MARKETPLACE_CHROME_BINARY`
- `MARKETPLACE_ARTIFACTS_DIR`
- `MARKETPLACE_PROFILE_DIR`

## API HTTP

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Interface web |
| `GET` | `/api/info` | Informações da API e do diretório de dados |
| `GET` | `/api/health` | Verificação de disponibilidade |
| `POST` | `/api/search` | Pesquisa em uma ou mais plataformas |
| `GET` ou `POST` | `/scrape/olx` | Pesquisa na OLX |
| `GET` ou `POST` | `/scrape/mercadolivre` | Pesquisa no Mercado Livre |
| `GET` ou `POST` | `/scrape/kabum` | Pesquisa na KaBuM |
| `GET` ou `POST` | `/scrape/terabyte` | Pesquisa na Terabyte |
| `GET` ou `POST` | `/scrape/pcgamerbrasilia` | Pesquisa na PC Gamer Brasília |
| `GET` ou `POST` | `/scrape/aliexpress` | Pesquisa no AliExpress |
| `GET` ou `POST` | `/scrape/facebook` | Pesquisa no Facebook |
| `GET` ou `POST` | `/scrape/both` | Pesquisa em duas plataformas |

Exemplo de requisição para `POST /api/search`:

```json
{
  "query": "gtx 1060",
  "platforms": ["olx", "mercadolivre"],
  "max_results": 8,
  "headless": false
}
```

## Estrutura do projeto

- `main.py`: API FastAPI e interface de linha de comando do servidor.
- `marketplace_scraper.py`: scrapers Selenium, filtros e análise dos resultados.
- `marketplace_search/settings.py`: configurações e diretórios de execução.
- `marketplace_search/ui.html`: interface web.
- `launcher.py`: preparação do ambiente e inicialização da aplicação.
- `pyproject.toml`: metadados e configuração de instalação do pacote.

## Observações de uso

- O Selenium procura o Chrome configurado em `MARKETPLACE_CHROME_BINARY` e também verifica os diretórios locais previstos pela aplicação.
- Algumas consultas exigem uma janela de navegador visível. O modo sem interface pode não funcionar em plataformas que solicitam verificação adicional.
- O cache de consultas tem duração padrão de 120 segundos.
- A busca múltipla executa as consultas em paralelo.
- A gravação de snapshots HTML de consultas bem-sucedidas fica desativada por padrão; pode ser habilitada por `MARKETPLACE_SAVE_SUCCESS_HTML_SNAPSHOTS`.
- Algumas plataformas podem apresentar captcha, autenticação ou mecanismos de proteção. No Facebook, pode ser necessário entrar manualmente na primeira execução; o perfil do navegador é persistido no diretório de dados da aplicação.
