"""
Download BE TDS van Sikkens.be en Trimetal.be
==============================================
Gebruik:
  1. Zorg dat sikkens_tds_urls.json en trimetal_tds_urls.json
     in dezelfde map staan als dit script (of in Downloads).
  2. Installeer requests als je dat nog niet hebt:
       pip install requests
  3. Draai het script:
       python3 download_BE_TDS.py

Het script:
  - Leest de URL-lijsten uit de JSON-bestanden
  - Hernoemt elke PDF naar: BE_PROF_Sikkens_Product_TDS.pdf
  - Slaat op in de juiste submappen van SmartPaintSupport
  - Slaat bestaande bestanden over
"""

import json
import re
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Installeer eerst requests:  pip install requests")
    sys.exit(1)

# ─── PADEN ───────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).parent
SIKKENS_DIR  = SCRIPT_DIR / "BE markt" / "PROF" / "BE Sikkens"  / "BE TDS Sikkens"
TRIMETAL_DIR = SCRIPT_DIR / "BE markt" / "PROF" / "BE Trimetal" / "BE TDS Trimetal"

# Zoek JSON-bestanden in script-map of Downloads
def find_json(name):
    candidates = [
        SCRIPT_DIR / name,
        Path.home() / "Downloads" / name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

# ─── NAAM OPSCHONEN ──────────────────────────────────────────────────────────

def clean_product_name(url):
    name = url.split("/")[-1].replace(".pdf", "")
    # Verwijder bekende technische suffixen
    name = re.sub(r"_tns\d*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_tnt\d*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.\d+$", "", name)
    name = re.sub(r"_n\d{2}$", "", name)
    name = re.sub(r"_w\d{2}$", "", name)
    name = re.sub(r"_\d{8}.*$", "", name)
    name = re.sub(r"_du_.*$", "", name)
    name = re.sub(r"_validit.*$", "", name)
    name = re.sub(r"_iac_.*$", "", name)
    # Verwijder markt-prefix
    name = re.sub(r"^(si|tr)_be_(nl|fr)_", "", name, flags=re.IGNORECASE)
    # Verwijder voorloopgetallen (bijv. 392202300352204_)
    name = re.sub(r"^\d+_", "", name)
    # Opschonen en kapitaliseren
    name = re.sub(r"_+", "_", name).strip("_")
    name = "_".join(w.capitalize() for w in name.split("_") if w)
    return name

# ─── DOWNLOAD ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
    "Referer": "https://www.sikkens.be/",
}

def download_pdf(url, dest: Path) -> str:
    """Download één PDF. Geeft 'ok', 'skip' of 'err' terug."""
    if dest.exists():
        return "skip"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and "pdf" in r.headers.get("content-type", ""):
            dest.write_bytes(r.content)
            return "ok"
        else:
            return f"err:{r.status_code}"
    except Exception as e:
        return f"err:{e}"

def process_brand(json_path, dest_dir: Path, merk: str):
    with open(json_path) as f:
        data = json.load(f)
    urls = data.get(merk.lower(), data.get(list(data.keys())[0], []))

    dest_dir.mkdir(parents=True, exist_ok=True)

    ok = skip = err = 0
    seen_names = set()

    for url in urls:
        product = clean_product_name(url)
        filename = f"BE_PROF_{merk}_{product}_TDS.pdf"

        # Dedupliceer op naam
        if filename in seen_names:
            continue
        seen_names.add(filename)

        result = download_pdf(url, dest_dir / filename)
        if result == "ok":
            print(f"  ✅ {filename}")
            ok += 1
        elif result == "skip":
            print(f"  ⏭️  {filename} (al aanwezig)")
            skip += 1
        else:
            print(f"  ❌ {filename} — {result}")
            err += 1

    return ok, skip, err

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BE TDS Downloader — Sikkens & Trimetal")
    print("=" * 60)

    totals = {}

    for merk, json_name, dest_dir in [
        ("Sikkens",  "sikkens_tds_urls.json",  SIKKENS_DIR),
        ("Trimetal", "trimetal_tds_urls.json",  TRIMETAL_DIR),
    ]:
        json_path = find_json(json_name)
        if not json_path:
            print(f"\n⚠️  {json_name} niet gevonden. Verwacht in:")
            print(f"   • {SCRIPT_DIR / json_name}")
            print(f"   • {Path.home() / 'Downloads' / json_name}")
            continue

        print(f"\n📥  {merk.upper()} BE  ({json_path})")
        print("-" * 40)
        ok, skip, err = process_brand(json_path, dest_dir, merk)
        totals[merk] = (ok, skip, err)

    print("\n" + "=" * 60)
    print("KLAAR")
    print("=" * 60)
    for merk, (ok, skip, err) in totals.items():
        print(f"{merk:10} ✅ {ok} gedownload  ⏭️  {skip} al aanwezig  ❌ {err} fouten")
    print(f"\nOpgeslagen in:")
    print(f"  {SIKKENS_DIR}")
    print(f"  {TRIMETAL_DIR}")

if __name__ == "__main__":
    main()
