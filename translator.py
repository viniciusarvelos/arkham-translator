import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    print("Você precisa instalar o pacote openai: pip install openai", file=sys.stderr)
    sys.exit(1)

# --- Config OpenAI ---
DEFAULT_MODEL = "gpt-5"
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0  # segundos * (2^tentativa)

TRANSLATABLE_FIELDS = ["name", "subname", "text", "flavor", "traits"]
ICON_PATTERN = re.compile(r"\[\w+\]")

def load_env_dotenv():
    """Carrega .env se existir (sem dependência externa)."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

class Cache:
    """Cache simples em SQLite para traduções idempotentes."""
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                src TEXT NOT NULL,
                tgt TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get(self, key: str) -> Optional[str]:
        cur = self.conn.execute("SELECT tgt FROM cache WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set(self, key: str, src: str, tgt: str, model: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO cache(key, src, tgt, model, created_at) VALUES(?,?,?,?,?)",
            (key, src, tgt, model, datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()

def build_prompt(text: str, glossary: Dict[str, str]) -> str:
    gloss_lines = "\n".join(f"- {k} -> {v}" for k, v in glossary.items())
    return f"""
Você é um tradutor especializado no jogo de cartas "Arkham Horror: The Card Game".
Traduza o conteúdo a seguir para **português do Brasil**, mantendo a precisão de regras e a naturalidade.
Regras importantes:
- Preserve marcadores, ícones e símbolos entre colchetes (ex.: [action], [skull]) exatamente como estão.
- Não altere tags de formatação ou placeholders ({{x}}, {{n}}, etc.).
- Mantenha a capitalização de nomes próprios e lugares.
- Aplique SEMPRE o glossário (consistência é obrigatória).
- Gere traduções **determinísticas**: para o mesmo texto e glossário, o resultado deve ser **exatamente igual**.
- Evite sinônimos ou variações de estilo; traduza de forma consistente com traduções anteriores.

Glossário (EN -> PT-BR):
{gloss_lines}

Texto a traduzir (sem comentários adicionais, apenas o texto traduzido):
{text}
""".strip()

def apply_glossary_post(text: str, glossary: Dict[str, str]) -> str:
    """Substituição adicional respeitando bordas de palavra, sem quebrar maiúsculas/símbolos."""
    for en, pt in sorted(glossary.items(), key=lambda kv: len(kv[0]), reverse=True):
        pattern = r"(?<!\w)" + re.escape(en) + r"(?!\w)"
        text = re.sub(pattern, pt, text)
    return text

def translate_via_openai(client: OpenAI, model: str, src_text: str, glossary: Dict[str, str]) -> str:
    """Chama a API da OpenAI com retries e fallback de endpoint."""
    prompt = build_prompt(src_text, glossary)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Tenta usar Responses API
            try:
                resp = client.responses.create(
                    model=model,
                    input=prompt
                )
                if hasattr(resp, "output_text"):
                    return resp.output_text.strip()
                if hasattr(resp, "choices") and resp.choices:
                    return resp.choices[0].message.content.strip()
            except Exception:
                # Fallback para Chat Completions
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            sleep_for = RETRY_BACKOFF * (2 ** (attempt - 1))
            print(f"[WARN] Erro na tradução (tentativa {attempt}/{MAX_RETRIES}): {e}. Retentando em {sleep_for:.1f}s...", file=sys.stderr)
            time.sleep(sleep_for)
    raise RuntimeError(f"Falha ao traduzir após {MAX_RETRIES} tentativas: {last_err}")

def is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")

def find_json_files(root: Path, packs_filter: List[str]) -> List[Path]:
    """Encontra arquivos JSON na pasta /source do projeto."""
    source_dir = root / "source"
    if not source_dir.exists():
        print(f"[WARN] Diretório {source_dir} não encontrado.")
        return []
    files = [f for f in source_dir.glob("*.json")]
    if packs_filter:
        files = [f for f in files if any(p in f.name for p in packs_filter)]
    return sorted(files)

def rate_limit_sleep(rate_per_minute: int, started_at: float, calls_made: int):
    """Mantém taxa aproximada (RPS ~ rate/60)."""
    if rate_per_minute <= 0:
        return
    ideal_elapsed = calls_made * (60.0 / rate_per_minute)
    actual_elapsed = time.time() - started_at
    if ideal_elapsed > actual_elapsed:
        time.sleep(ideal_elapsed - actual_elapsed)

def process_file(
    path: Path, out_dir: Path, client: OpenAI, model: str,
    glossary: Dict[str, str], cache: Cache, dry_run: bool,
    rate_per_min: int
) -> Dict[str, int]:
    """Traduz um arquivo JSON de cartas e grava JSON/CSV."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERRO] Falha ao ler {path}: {e}", file=sys.stderr)
        return {"translated": 0, "skipped": 0}

    if not isinstance(data, list):
        print(f"[WARN] {path} não parece uma lista de cartas; ignorando.")
        return {"translated": 0, "skipped": 0}

    out_cards: List[Dict[str, Any]] = []
    csv_rows: List[Dict[str, str]] = []

    start = time.time()
    calls = 0
    skipped = 0

    for card in data:
        card_out = dict(card)
        for field in TRANSLATABLE_FIELDS:
            src = card.get(field, "")
            if is_empty(src) or not isinstance(src, str):
                skipped += 1
                continue

            key = sha1(f"{model}:{field}:{src}")
            cached = cache.get(key)
            if cached:
                translated = cached
            else:
                calls += 1
                rate_limit_sleep(rate_per_min, start, calls)
                translated = translate_via_openai(client, model, src, glossary)
                translated = apply_glossary_post(translated, glossary)
                cache.set(key, src, translated, model)

            card_out[f"{field}_pt"] = translated
            csv_rows.append({
                "code": str(card.get("code", "")),
                "field": field,
                "en": src,
                "pt": translated,
                "pack_file": str(path)
            })
        out_cards.append(card_out)

    rel = path.relative_to(path.parents[1]) if "pack" in str(path) else path.name
    out_json = out_dir / rel
    out_csv = out_dir / "csv" / (path.stem + "_pt.csv")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not dry_run:
        out_json.write_text(json.dumps(out_cards, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "field", "en", "pt", "pack_file"])
        writer.writeheader()
        writer.writerows(csv_rows)

    return {"translated": len(csv_rows), "skipped": skipped}

def main():
    load_env_dotenv()
    parser = argparse.ArgumentParser(description="Tradutor ArkhamDB → PT-BR (OpenAI GPT)")
    parser.add_argument("--root", required=True, help="Caminho do repo arkhamdb-json-data clonado localmente")
    parser.add_argument("--packs", default="", help="Lista de pastas de pack (ex: tde,win,tic). Vazio = todos.")
    parser.add_argument("--out", default="out", help="Diretório de saída (JSON/CSV)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo OpenAI (ex: gpt-5, gpt-5-mini)")
    parser.add_argument("--dry-run", action="store_true", help="Não salvar JSONs traduzidos")
    parser.add_argument("--rate", type=int, default=30, help="limite por minuto (aprox)")
    parser.add_argument("--cache", default=".cache.sqlite", help="arquivo SQLite de cache")
    parser.add_argument("--glossary", default="glossary.json", help="arquivo JSON com glossário (EN->PT)")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Erro: defina OPENAI_API_KEY no ambiente ou .env", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    packs_filter = [p.strip() for p in args.packs.split(",") if p.strip()]
    json_files = find_json_files(root, packs_filter)
    if not json_files:
        print(f"Nenhum JSON encontrado em {root}/source com filtro={packs_filter or 'todos'}")
        sys.exit(1)

    # Carrega glossário
    if Path(args.glossary).exists():
        glossary = json.loads(Path(args.glossary).read_text(encoding="utf-8"))
    else:
        print(f"[WARN] Glossário {args.glossary} não encontrado; usando dicionário mínimo.")
        glossary = {
            "Clue": "Pista",
            "Clues": "Pistas",
            "Doom": "Perdição",
            "Chaos Bag": "Saco do Caos",
            "Skill Test": "Teste de Perícia",
            "Evade": "Evadir",
            "Engage": "Engajar",
            "Scenario": "Cenário",
            "Campaign": "Campanha",
            "Exhaust": "Exaurir",
            "Exhausted": "Exaurido",
        }

    cache = Cache(Path(args.cache))
    totals = {"translated": 0, "skipped": 0}

    for jf in json_files:
        stats = process_file(
            path=jf,
            out_dir=out_dir,
            client=client,
            model=args.model,
            glossary=glossary,
            cache=cache,
            dry_run=args.dry_run,
            rate_per_min=args.rate
        )
        totals["translated"] += stats["translated"]
        totals["skipped"] += stats["skipped"]
        print(f"[OK] {jf.name}: +{stats['translated']} campos traduzidos, {stats['skipped']} ignorados")

    print(f"\nConcluído. Total traduzido: {totals['translated']} campos. Ignorados: {totals['skipped']}.")
    print(f"Saídas: JSON em {out_dir} e CSV em {out_dir/'csv'}")
    print("Dica: faça o review no CSV e depois aplique merge de volta aos JSONs conforme necessário.")

if __name__ == "__main__":
    main()
