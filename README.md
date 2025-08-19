# Arkham Horror Card Translator

A Python-based project to extract JSON card data, convert it to CSV, and translate content into **Brazilian Portuguese** using the OpenAI GPT API, preserving game terminology and formatting.

---

## 👂 Project Structure

```
project/
├── Dockerfile
├── docker-compose.yml
├── json_to_csv.py           # Converts JSON files to CSV
├── translate_csv.py         # Translates CSV content using GPT
├── source/                  # Input JSON files
├── app/
│   └── glossary/            # Glossary JSON files to preserve terms
└── out/                     # Output folder for CSVs
```

---

## 🛠 Features

* Converts multiple JSON files from `/source` into a single CSV.
* Preserves only relevant fields:

  * `code`
  * `name`
  * `subname`
  * `text`
  * `traits`
  * `flavor`
  * `back_text`
  * `back_flavor`
* Translates CSV content into Brazilian Portuguese using GPT.
* Glossary-based term replacement ensures consistent translations.
* Batches multiple rows per API call to save tokens.
* Dockerized for easy reproducibility.

---

## ⚡ Requirements

* Docker & Docker Compose
* OpenAI API key

---

## 👳 Docker Setup

1. **Build Docker image:**

```bash
docker compose build
```

2. **Set your OpenAI API key** (either in `.env` or environment variable):

```bash
export OPENAI_API_KEY="your_api_key_here"
```

---

## 🚀 Usage

### 1️⃣ Extract JSON → CSV

```bash
docker compose run --rm extract
```

* Output CSV will be saved in `/out/output.csv`.

### 2️⃣ Translate CSV → Translated CSV

```bash
docker compose run --rm translate
```

* Uses `/out/output.csv` as input.
* Produces `/out/output_translated.csv`.

---

## 🗑 Glossary

* Place glossary JSON files in `/glossary/`.
* Each file should be a JSON mapping of English → Portuguese terms, for example:

```json
{
  "Skull": "Caveira",
  "Cultist": "Sectário"
}
```

* Terms will be replaced by placeholders during translation to **save tokens and ensure consistency**.

---

## ⚙ Configuration

* **Batch size** for translation can be adjusted in `translate_csv.py` via `BATCH_SIZE`.
* **Output folder**: `/out`
* **Source folder**: `/source`
* **Glossary folder**: `/glossary`

---

## 🤠 Notes

* Translations are deterministic (`temperature=0`) for reproducibility.
* Placeholders ensure symbols, formatting, and game terms remain intact.
* Supports batch processing to reduce API calls and token usage.

---

## 🔗 References

* [OpenAI Python SDK](https://github.com/openai/openai-python)
* [Arkham Horror: The Card Game](https://www.fantasyflightgames.com/en/products/arkham-horror-card-game/)
