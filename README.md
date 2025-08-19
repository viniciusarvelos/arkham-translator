# Tradutor de Arkham Horror Card Game

Um projeto em Python para extrair dados de cartas em JSON, converter em CSV e traduzir o conteúdo para **português do Brasil** usando a API GPT da OpenAI, preservando a terminologia e a formatação do jogo.

---

## 📂 Estrutura do Projeto

```
project/
├── Dockerfile
├── docker-compose.yml
├── json_to_csv.py           # Converte arquivos JSON em CSV
├── translate_csv.py         # Traduz o conteúdo do CSV usando GPT
├── source/                  # Arquivos JSON de entrada
├── app/
│   └── glossary/            # Arquivos JSON de glossário para preservar termos
└── out/                     # Pasta de saída para os CSVs
```

---

## 🛠 Funcionalidades

* Converte múltiplos arquivos JSON de `/source` em um único CSV.
* Preserva apenas os campos relevantes:

  * `code`
  * `name`
  * `subname`
  * `text`
  * `traits`
  * `flavor`
  * `back_text`
  * `back_flavor`
* Traduz o conteúdo do CSV para português do Brasil usando GPT.
* Substituição baseada em glossário garante traduções consistentes.
* Processa múltiplas linhas por chamada de API para economizar tokens.
* Dockerizado para fácil reprodução.

---

## ⚡ Requisitos

* Docker & Docker Compose
* Chave da API OpenAI

---

## 🐳 Configuração Docker

1. **Construir a imagem Docker:**

```bash
docker compose build
```

2. **Definir sua chave da API OpenAI** (no `.env` ou como variável de ambiente):

```bash
export OPENAI_API_KEY="sua_chave_aqui"
```

---

## 🚀 Uso

### 1️⃣ Extrair JSON → CSV

```bash
docker compose run --rm extract
```

* O CSV de saída será salvo em `/out/output.csv`.

### 2️⃣ Traduzir CSV → CSV Traduzido

```bash
docker compose run --rm translate
```

* Usa `/out/output.csv` como entrada.
* Gera `/out/output_translated.csv`.

---

## 📝 Glossário

* Coloque os arquivos JSON de glossário em `/app/glossary/`.
* Cada arquivo deve mapear termos em inglês → português, por exemplo:

```json
{
  "Doom": "Perdição",
  "Clue": "Pista"
}
```

* Os termos serão substituídos por placeholders durante a tradução para **economizar tokens e garantir consistência**.

---

## ⚙ Configuração

* O **tamanho do lote** para tradução pode ser ajustado em `translate_csv.py` através de `BATCH_SIZE`.
* **Pasta de saída**: `/out`
* **Pasta de origem**: `/source`
* **Pasta de glossário**: `/app/glossary`

---

## 🧠 Observações

* As traduções são determinísticas (`temperature=0`) para garantir reprodutibilidade.
* Placeholders garantem que símbolos, formatação e termos do jogo permaneçam intactos.
* Suporta processamento em lote para reduzir chamadas de API e uso de tokens.

---

## 🔗 Referências

* [OpenAI Python SDK](https://github.com/openai/openai-python)
* [Arkham Horror: The Card Game](https://www.fantasyflightgames.com/en/products/arkham-horror-card-game/)
