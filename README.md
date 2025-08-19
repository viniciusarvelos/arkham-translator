ArkhamDB → PT-BR Translator (GPT API)
-------------------------------------
- Lê JSONs do repositório arkhamdb-json-data (packs/campaigns).
- Tradução com OpenAI API (GPT-5 por padrão), com cache local (SQLite).
- Aplica glossário fixo e normalizações.
- Exporta CSV para revisão comunitária e regrava JSON com campos *_pt.
- Suporta retomada, dry-run e limitação de taxa.

Uso:
  python translator.py \
      --root ~/repos/arkhamdb-json-data \
      --packs tde,win,tic \
      --out out \
      --model gpt-5 \
      --dry-run false \
      --rate 30

Pré-requisitos:
  - pip install -r requirements.txt
  - Defina OPENAI_API_KEY no ambiente ou .env
