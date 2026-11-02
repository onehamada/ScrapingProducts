PROJETO - ENGENHARIA DE SOFTWARE - ESTACIO PISTAL SUL, DF
INTEGRANTES:
Wesley Gabriel Batista Rosa - 202601418793
Guilherme Araujo - 202408147627
Marcely Bomfim Barella - 202603316301
Fernando Miguel Costa Cardoso  -  202601835904
Stenio Daniel Santos de Araújo - 202607148283



# Marketplace Search

Aplicacao local para pesquisar produtos em marketplaces com FastAPI, Selenium e uma interface web unica. O projeto foi refinado para funcionar melhor como app independente: configuracao centralizada, comando proprio de execucao e workspace separado do codigo.

## Objetivo

Desenvolver uma aplicacao local para pesquisar e comparar produtos em diferentes marketplaces, reunindo resultados e oportunidades de compra em uma unica interface.

## O que o app entrega

- Busca em OLX, Mercado Livre, KaBuM, Terabyte, PC Gamer Brasilia, AliExpress e Facebook
- Interface web em `/` com busca unica, radar comercial e exportacao
- Busca paralela entre plataformas
- Cache curto para consultas repetidas
- Perfil de hardware e filtros automaticos a partir do texto digitado
- Filtro automatico por titulo, perfil detectado e variacoes de query
- Comparativo comercial com mediana filtrada, menor preco e oportunidades
- Exportacao em CSV e resumo comercial pronto para copiar
- Endpoints JSON para integracao

## Como rodar a partir do codigo

Use Python 3.11 a 3.14 (recomendado: Python 3.13). O Python 3.15 ainda nao e compativel com as dependencias fixadas neste projeto.

1. Instale as dependencias:

```bash
pip install -r requirements.txt
```

2. Inicie a aplicacao:

```bash
python -m marketplace_search
```

3. A interface abre em:

```text
http://127.0.0.1:8000
```

Voce tambem pode controlar host, porta e navegador:

```bash
python -m marketplace_search --host 127.0.0.1 --port 8000 --no-browser
```

## Inicializacao automatica no Windows

Se quiser abrir com duplo clique:

```text
start_marketplace.bat
```

Ou via launcher:

```bash
python launcher.py
```

O launcher:

- cria um ambiente virtual separado por versao do Python automaticamente, se necessario
- atualiza o `pip` na primeira execucao
- instala ou atualiza as dependencias
- inicia o modulo `marketplace_search`
- pode buscar atualizacoes no GitHub antes de abrir o app

Para apenas preparar o ambiente:

```bash
python launcher.py --bootstrap-only
```

## Atualizacao automatica em outra maquina

O caminho mais simples para distribuir com update automatico e mandar a pasta do projeto com o `start_marketplace.bat` e deixar o usuario abrir sempre por ele.

O `.bat` ja liga `MARKETPLACE_AUTO_UPDATE=true` por padrao, entao a cada abertura o launcher:

- consulta o repositorio no GitHub
- compara a versao atual ou o commit instalado
- baixa a ultima versao da branch configurada
- atualiza os arquivos do projeto
- reinicia o launcher e abre o app

Comandos uteis:

```bash
python launcher.py --auto-update
python launcher.py --update-only
python launcher.py --skip-update
```

Variaveis de ambiente para controlar isso:

- `MARKETPLACE_AUTO_UPDATE`
- `MARKETPLACE_UPDATE_REPO`
- `MARKETPLACE_UPDATE_BRANCH`
- `MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS`

Fluxo recomendado:

1. Voce sobe as alteracoes no GitHub.
2. A outra maquina abre o app pelo `start_marketplace.bat`.
3. O launcher baixa a nova versao sozinho.

Observacao: para o updater encontrar melhor as mudancas, mantenha a branch de distribuicao no GitHub atualizada. Se voce quiser uma esteira mais controlada, use a `main` so para versoes liberadas.

## Instalacao como aplicacao

Agora o projeto tambem pode ser instalado como pacote local:

```bash
pip install .
marketplace-search
```

## Workspace independente

Por padrao, os dados de runtime nao ficam mais misturados ao codigo.

- No Windows, o workspace padrao fica em `%LOCALAPPDATA%\MarketplaceSearch`
- Fora do Windows, o padrao e `~/.marketplace-search`
- Artefatos HTML e JSON ficam em `artifacts/` dentro desse workspace
- Perfis persistentes do Selenium ficam em `profiles/` dentro desse workspace
- Estado interno do launcher fica em `launcher/` dentro desse workspace

Voce pode personalizar isso com um arquivo `.env` ou variaveis de ambiente. Existe um modelo em `.env.example`.

Variaveis principais:

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

## Endpoints principais

- `GET /` -> interface web
- `GET /api/info` -> informacoes da API e do workspace atual
- `GET /api/health` -> health check
- `POST /api/search` -> busca multipla
- `GET|POST /scrape/olx`
- `GET|POST /scrape/mercadolivre`
- `GET|POST /scrape/kabum`
- `GET|POST /scrape/terabyte`
- `GET|POST /scrape/pcgamerbrasilia`
- `GET|POST /scrape/aliexpress`
- `GET|POST /scrape/facebook`
- `GET|POST /scrape/both`

## Exemplo de chamada JSON

```json
POST /api/search
{
  "query": "gtx 1060",
  "platforms": ["olx", "mercadolivre"],
  "max_results": 8,
  "headless": false
}
```

## Estrutura principal

- `main.py` -> API FastAPI e CLI do servidor
- `marketplace_scraper.py` -> scrapers Selenium, filtros e analise comercial
- `marketplace_search/settings.py` -> configuracao centralizada e workspace do app
- `marketplace_search/ui.html` -> interface web
- `launcher.py` -> bootstrap local no Windows ou em dev
- `pyproject.toml` -> metadata para instalar o projeto como app

## Observacoes praticas

- O Selenium procura um Chrome local primeiro no workspace da aplicacao e depois em `chrome-win64` no projeto.
- As buscas podem abrir uma janela real do navegador. Isso e proposital, porque muitos sites bloqueiam navegacao headless.
- Consultas repetidas iguais podem voltar do cache por ate 120 segundos por padrao.
- Em buscas multiplas, a API roda as plataformas em paralelo para reduzir o tempo total.
- Dumps HTML de buscas bem-sucedidas ficam desligados por padrao para reduzir I/O; voce pode religar isso no `.env`.
- KaBuM extrai os produtos pelo JSON embutido da propria pagina de busca.
- Terabyte pode ativar protecao anti-bot em algumas tentativas, principalmente em ambientes muito automatizados.
- PC Gamer Brasilia usa navegador real porque o site pode bloquear requisicoes diretas em algumas tentativas.
- AliExpress pode pedir captcha ou verificacao manual; ela tende a funcionar melhor com `headless=false`.
- Para o Facebook, rode com `headless=false`. Na primeira execucao o navegador pode ficar aberto por alguns minutos para voce fazer login manual usando o perfil persistente do workspace.
