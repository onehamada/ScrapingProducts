# 🛒✨ Marketplace Search

> Chega de abrir 7 abas pra caçar a melhor oferta! 🔎💸
> Pesquise **uma vez** e compare preços em vários marketplaces de uma só vez. 🚀

---

## 🎓 Sobre o projeto

**Projeto de Engenharia de Software — Estácio Pistão Sul, DF** 💙

### 👥 A squad

| Nome | Matrícula |
|------|-----------|
| 😎 Wesley Gabriel Batista Rosa | 202601418793 |
| 🚀 Guilherme Araujo | 202408147627 |
| 🌟 Marcely Bomfim Barella | 202603316301 |
| 🔥 Fernando Miguel Costa Cardoso | 202601835904 |
| 💻 Stenio Daniel Santos de Araújo | 202607148283 |

---

## 🎯 Qual é a ideia?

Um app local que pesquisa e compara produtos em vários marketplaces, juntando resultados e oportunidades de compra numa interface única. Feito com **FastAPI + Selenium** 🐍⚡

## 🎁 O que o app faz

- 🛍️ Busca em **OLX, Mercado Livre, KaBuM, Terabyte, PC Gamer Brasília, AliExpress e Facebook**
- 🖥️ Interface web em `/` com busca única, radar comercial e exportação
- ⚡ Busca paralela entre as plataformas (bem mais rápido!)
- 🧠 Cache curto pra consultas repetidas
- 🎮 Perfil de hardware e filtros automáticos a partir do texto que você digita
- 🧹 Filtro inteligente por título, perfil detectado e variações de query
- 📊 Comparativo comercial: mediana filtrada, menor preço e oportunidades
- 📥 Exportação em CSV + resumo comercial pronto pra copiar
- 🔌 Endpoints JSON pra integrar com o que você quiser

---

## 🏁 Bora rodar?

> 🐍 Use **Python 3.11 a 3.14** (recomendado: **3.13**). O Python 3.15 ainda não é compatível com as dependências fixadas.

**1️⃣ Instale as dependências:**

```bash
pip install -r requirements.txt
```

**2️⃣ Inicie o app:**

```bash
python -m marketplace_search
```

**3️⃣ Abra no navegador:** 🌐

```text
http://127.0.0.1:8000
```

Quer mexer em host, porta e navegador? Dá pra fazer 🛠️

```bash
python -m marketplace_search --host 127.0.0.1 --port 8000 --no-browser
```

---

## 🪟 Modo preguiça no Windows (duplo clique!)

```text
start_marketplace.bat
```

Ou pelo launcher:

```bash
python launcher.py
```

### 🤖 O que o launcher faz por você

- 🧪 Cria um ambiente virtual separado por versão do Python (se precisar)
- ⬆️ Atualiza o `pip` na primeira execução
- 📦 Instala/atualiza as dependências
- ▶️ Inicia o módulo `marketplace_search`
- 🔄 Pode buscar atualizações no GitHub antes de abrir

Só quer preparar o ambiente?

```bash
python launcher.py --bootstrap-only
```

---

## 🔄 Atualização automática em outra máquina

O jeito mais fácil: mande a pasta do projeto com o `start_marketplace.bat` e peça pra pessoa **sempre abrir por ele** 😉

O `.bat` já liga `MARKETPLACE_AUTO_UPDATE=true` por padrão. A cada abertura, o launcher:

1. 🔍 Consulta o repositório no GitHub
2. ⚖️ Compara a versão atual ou o commit instalado
3. ⬇️ Baixa a última versão da branch configurada
4. 📝 Atualiza os arquivos do projeto
5. 🔁 Reinicia o launcher e abre o app

**Comandos úteis:**

```bash
python launcher.py --auto-update
python launcher.py --update-only
python launcher.py --skip-update
```

**Variáveis de ambiente:**

- `MARKETPLACE_AUTO_UPDATE`
- `MARKETPLACE_UPDATE_REPO`
- `MARKETPLACE_UPDATE_BRANCH`
- `MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS`

**Fluxo recomendado:**

1. 📤 Você sobe as alterações no GitHub
2. 🖱️ A outra máquina abre o app pelo `start_marketplace.bat`
3. 🎉 O launcher baixa a nova versão sozinho!

> 💡 **Dica:** mantenha a branch de distribuição sempre atualizada. Quer um fluxo mais controlado? Use a `main` só para versões liberadas.

---

## 📦 Instalação como aplicação

O projeto também pode ser instalado como pacote local:

```bash
pip install .
marketplace-search
```

---

## 🗂️ Workspace independente

Os dados de runtime **não ficam misturados com o código** 🧼

- 🪟 No Windows: `%LOCALAPPDATA%\MarketplaceSearch`
- 🐧🍎 Fora do Windows: `~/.marketplace-search`
- 🧾 Artefatos HTML e JSON ficam em `artifacts/`
- 👤 Perfis persistentes do Selenium ficam em `profiles/`
- 🚀 Estado interno do launcher fica em `launcher/`

Dá pra personalizar tudo com um arquivo `.env` ou variáveis de ambiente (tem um modelo no `.env.example`).

**Variáveis principais:**

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

---

## 🔌 Endpoints principais

| Método | Rota | Pra que serve |
|--------|------|---------------|
| `GET` | `/` | 🖥️ Interface web |
| `GET` | `/api/info` | ℹ️ Infos da API e do workspace |
| `GET` | `/api/health` | 💓 Health check |
| `POST` | `/api/search` | 🔎 Busca múltipla |
| `GET\|POST` | `/scrape/olx` | 🟣 OLX |
| `GET\|POST` | `/scrape/mercadolivre` | 🟡 Mercado Livre |
| `GET\|POST` | `/scrape/kabum` | 🟠 KaBuM |
| `GET\|POST` | `/scrape/terabyte` | 🟢 Terabyte |
| `GET\|POST` | `/scrape/pcgamerbrasilia` | 🎮 PC Gamer Brasília |
| `GET\|POST` | `/scrape/aliexpress` | 🔴 AliExpress |
| `GET\|POST` | `/scrape/facebook` | 🔵 Facebook |
| `GET\|POST` | `/scrape/both` | ✌️ Duas plataformas juntas |

### 📮 Exemplo de chamada JSON

```json
POST /api/search
{
  "query": "gtx 1060",
  "platforms": ["olx", "mercadolivre"],
  "max_results": 8,
  "headless": false
}
```

---

## 🧱 Estrutura principal

- 🐍 `main.py` → API FastAPI e CLI do servidor
- 🕷️ `marketplace_scraper.py` → scrapers Selenium, filtros e análise comercial
- ⚙️ `marketplace_search/settings.py` → configuração centralizada e workspace
- 🎨 `marketplace_search/ui.html` → interface web
- 🚀 `launcher.py` → bootstrap local no Windows ou em dev
- 📦 `pyproject.toml` → metadados pra instalar o projeto como app

---

## ⚠️ Dicas e pegadinhas

- 🌐 O Selenium procura um Chrome local primeiro no workspace da aplicação e depois em `chrome-win64` no projeto.
- 👀 As buscas podem abrir uma **janela real** do navegador. É de propósito: muitos sites bloqueiam navegação headless!
- ⏱️ Consultas repetidas voltam do cache por até **120 segundos** (padrão).
- ⚡ Em buscas múltiplas, as plataformas rodam em paralelo pra economizar tempo.
- 💾 Dumps HTML de buscas bem-sucedidas ficam desligados por padrão (menos I/O). Dá pra religar no `.env`.
- 🟠 **KaBuM:** extrai os produtos pelo JSON embutido na própria página de busca.
- 🟢 **Terabyte:** pode ativar proteção anti-bot em algumas tentativas, principalmente em ambientes muito automatizados.
- 🎮 **PC Gamer Brasília:** usa navegador real porque o site pode bloquear requisições diretas.
- 🔴 **AliExpress:** pode pedir captcha ou verificação manual. Funciona melhor com `headless=false`.
- 🔵 **Facebook:** rode com `headless=false`! Na primeira execução o navegador pode ficar aberto por alguns minutos pra você fazer login manual no perfil persistente do workspace.

---

<p align="center">Feito com 💙, ☕ e muito código pela squad da Estácio 🎓</p>
