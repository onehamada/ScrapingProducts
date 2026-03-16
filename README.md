# Marketplace Search

Aplicacao local para pesquisar produtos em marketplaces e ver os resultados em uma pagina com input.

## O que funciona

- Busca em **OLX** com Selenium
- Busca em **Mercado Livre** com Selenium
- Busca em **KaBuM** com Selenium
- Busca em **Terabyte** com Selenium
- Interface web em `/` com campo para digitar a pesquisa
- Busca paralela entre plataformas
- Cache curto para consultas repetidas
- Filtro automatico por titulo para manter apenas anuncios realmente parecidos com a busca
- Variacoes automaticas da query quando a primeira tentativa vem fraca
- Categoria `processador` com filtros especificos para CPU/Xeon
- Bloqueio de titulos com termos como `defeito`
- Media de precos com corte automatico de outliers
- Salvamento de HTML e JSON de cada busca em `artifacts/`
- Endpoints JSON para integracao

## O que ainda e limitado

- **Facebook Marketplace** continua em modo beta
- Em muitos casos o Facebook exige login e bloqueia scraping sem sessao autenticada
- OLX e Mercado Livre funcionam melhor com `headless=false`

## Como rodar

1. Instale as dependencias:

```bash
pip install -r requirements.txt
```

2. Inicie a aplicacao:

```bash
python main.py
```

3. O navegador local deve abrir automaticamente em:

```text
http://127.0.0.1:8000
```

## Inicializacao automatica no Windows

Se quiser abrir com duplo clique, use:

```text
start_marketplace.bat
```

Esse launcher:

- cria a pasta `.venv` automaticamente se ela nao existir
- atualiza o `pip` na primeira execucao
- instala ou atualiza as dependencias de `requirements.txt` quando necessario
- inicia a aplicacao em seguida

Opcionalmente voce tambem pode rodar:

```bash
python launcher.py
```

Ou apenas preparar o ambiente sem abrir a API:

```bash
python launcher.py --bootstrap-only
```

## Interface

Ao abrir a pagina inicial voce pode:

- digitar o termo da busca
- escolher OLX, Mercado Livre e Facebook
- escolher OLX, Mercado Livre, KaBuM, Terabyte e Facebook
- escolher a categoria manualmente ou deixar em `auto`
- definir o maximo de resultados
- ativar ou nao o modo invisivel

## Endpoints principais

- `GET /` -> interface com input
- `GET /api/info` -> informacoes da API
- `GET /api/health` -> health check
- `POST /api/search` -> busca multipla
- `GET|POST /scrape/olx`
- `GET|POST /scrape/mercadolivre`
- `GET|POST /scrape/kabum`
- `GET|POST /scrape/terabyte`
- `GET|POST /scrape/facebook`
- `GET|POST /scrape/both` -> OLX + Mercado Livre

## Exemplo de chamada JSON

```json
POST /api/search
{
  "query": "gtx 1060",
  "platforms": ["olx", "mercadolivre"],
  "category": "auto",
  "max_results": 8,
  "headless": false
}
```

## Estrutura importante

- `main.py` -> API FastAPI e pagina inicial
- `marketplace_scraper.py` -> scrapers Selenium e salvamento de artefatos
- `ui.html` -> interface com input e cards de resultado
- `artifacts/` -> HTML e JSON gerados a cada busca

## Observacoes praticas

- O Selenium usa o Chrome local da pasta `chrome-win64` quando ele estiver presente.
- As buscas podem abrir uma janela real do navegador. Isso e proposital, porque muitos sites bloqueiam navegacao headless.
- Consultas repetidas iguais podem voltar do cache por ate 120 segundos para reduzir latencia.
- Em buscas multiplas, a API roda as plataformas em paralelo para reduzir o tempo total.
- KaBuM extrai os produtos pelo JSON embutido da propria pagina de busca.
- Terabyte pode ativar protecao anti-bot em algumas tentativas, principalmente em ambientes muito automatizados.
- Para o Facebook, rode com `headless=false`. Na primeira execucao o navegador pode ficar aberto por ate 3 minutos para voce fazer login manual usando o perfil salvo em `.selenium-profiles/facebook`. Nao feche a janela antes da resposta voltar para a aplicacao.
- As buscas do Facebook usam por padrao a regiao `saopaulo`, porque o Marketplace publico sem sessao e resolvido por cidade/regiao, nao por pais inteiro.
