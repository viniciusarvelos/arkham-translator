import os
import json
import csv
import openai
from textwrap import dedent

# ========= CONFIG =========
INPUT_FILE = "./out/output.csv"
OUTPUT_FILE = "./out/output_translated.csv"
GLOSSARY_FOLDER = "./glossary"

FIELDS = ["code", "name", "subname", "text", "traits", "flavor", "back_text", "back_flavor"]

BATCH_SIZE = 10  # how many rows per API call (tune based on token size)


# Load glossary terms from JSON files in glossary
def load_glossary():
    glossary = {}
    placeholder_id = 1
    for filename in os.listdir(GLOSSARY_FOLDER):
        if filename.endswith(".json"):
            filepath = os.path.join(GLOSSARY_FOLDER, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print(f"⚠️ Skipping glossary file {filename}: invalid JSON")
                    continue

                if isinstance(data, dict):
                    for term, translation in data.items():
                        placeholder = f"__TERM{placeholder_id}__"
                        glossary[term] = {"placeholder": placeholder, "translation": translation}
                        placeholder_id += 1
    return glossary


# Replace glossary terms with placeholders
def apply_placeholders(text, glossary):
    for term, info in glossary.items():
        text = text.replace(term, info["placeholder"])
    return text


# Restore glossary terms (Portuguese translations)
def restore_terms(text, glossary):
    for term, info in glossary.items():
        text = text.replace(info["placeholder"], info["translation"])
    return text


# Translate a batch of rows at once
def translate_batch(rows, client, glossary):
    # Build structured text for translation
    batch_text = []
    for idx, row in enumerate(rows):
        entry_lines = [f"### ENTRY {idx} ###"]
        for field in FIELDS:
            value = row[field].strip() if row[field] else ""
            value = apply_placeholders(value, glossary)
            entry_lines.append(f"{field}: {value}")
        batch_text.append("\n".join(entry_lines))

    full_text = "\n\n".join(batch_text)

    prompt = dedent(f"""
    Você é um tradutor especializado no jogo de cartas "Arkham Horror: The Card Game".
    Traduza o conteúdo a seguir para **português do Brasil**, mantendo a precisão de regras e a naturalidade.

    Regras importantes:
    - Preserve marcadores, ícones e símbolos entre colchetes (ex.: [action], [skull]) exatamente como estão.
    - Não altere tags de formatação ou placeholders ({{{{x}}}}, {{{{n}}}}, etc.).
    - Mantenha a capitalização de nomes próprios e lugares.
    - Gere traduções **determinísticas**: para o mesmo texto e glossário, o resultado deve ser **exatamente igual**.
    - Evite sinônimos ou variações de estilo; traduza de forma consistente com traduções anteriores.

    Traduza mantendo a mesma estrutura. Não adicione comentários.
    {full_text}
    """)

    response = client.chat.completions.create(
        model="gpt-5",  # or gpt-4o-mini if you want cheaper/faster
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    translated_text = response.choices[0].message["content"].strip()

    # Parse translated response back into rows
    translated_rows = []
    current_row = {}
    for line in translated_text.splitlines():
        line = line.strip()
        if line.startswith("### ENTRY"):
            if current_row:
                translated_rows.append(current_row)
            current_row = {}
        elif ":" in line:
            field, val = line.split(":", 1)
            val = restore_terms(val.strip(), glossary)
            if field in FIELDS:
                current_row[field] = val
    if current_row:
        translated_rows.append(current_row)

    return translated_rows


def main():
    glossary = load_glossary()
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Read input CSV
    with open(INPUT_FILE, "r", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        all_rows = list(reader)

    translated_all = []
    for i in range(0, len(all_rows), BATCH_SIZE):
        batch = all_rows[i:i + BATCH_SIZE]
        print(f"🔄 Translating rows {i+1} to {i+len(batch)}...")
        translated = translate_batch(batch, client, glossary)
        translated_all.extend(translated)

    # Save translated CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(translated_all)

    print(f"✅ Translation complete. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
