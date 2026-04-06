"""
upload_naar_supabase.py — SmartTDS
Verwerkt alle 819 TDS bestanden van alle 16 merken naar Supabase.
Inclusief metadata: markt, segment, merk, categorie, producttype, etc.

Gebruik:
  python upload_naar_supabase.py
  python upload_naar_supabase.py --reset   (wist eerst alle bestaande records)
  python upload_naar_supabase.py --merk Sikkens  (verwerkt alleen 1 merk)
"""

import os
import sys
import csv
import argparse
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client
from sentence_transformers import SentenceTransformer

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv("Supabase.env.local")

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Map vanuit de repo root — pas aan naar jouw lokale SmartPaintSupport pad
BASE_DIR = Path(os.getenv("SMARTPAINT_DIR", "../SmartPaintSupport"))
METADATA_CSV = BASE_DIR / "master_metadata.csv"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# ── Merken definitie ──────────────────────────────────────────────────────────
MERKEN = [
    ("NL","DIY","Alabastine","NL","vulmiddelen",    "NL markt/DIY/NL Alabastine/NL TDS Alabastine"),
    ("NL","DIY","Cetabever",  "NL","houtbeits",     "NL markt/DIY/NL Cetabever/NL TDS Cetabever"),
    ("NL","DIY","Flexa",      "NL","verf-diy",      "NL markt/DIY/NL Flexa/NL TDS Flexa"),
    ("NL","DIY","Glitsa",     "NL","vloerlak",      "NL markt/DIY/NL Glitsa/NL TDS Glitsa"),
    ("NL","DIY","Hammerite",  "NL","metaalverf",    "NL markt/DIY/NL Hammerite/NL TDS Hammerite"),
    ("NL","PROF","Herbol",    "NL","verf-prof",     "NL markt/PROF/NL Herbol/NL TDS Herbol"),
    ("NL","PROF","Meesterhand","NL","applicatie",   "NL markt/PROF/NL Meesterhand/NL TDS Meesterhand"),
    ("NL","PROF","Sikkens",   "NL","verf-prof",     "NL markt/PROF/NL Sikkens/NL TDS Sikkens"),
    ("NL","PROF","Trimetal",  "NL","verf-prof",     "NL markt/PROF/NL Trimetal/NL TDS Trimetal"),
    ("BE","DIY","Dulux",      "NL","verf-diy",      "BE markt/DIY/BE Dulux/BE TDS Dulux"),
    ("BE","DIY","Hammerite",  "NL","metaalverf",    "BE markt/DIY/BE Hammerite/BE TDS Hammerite"),
    ("BE","DIY","Levis",      "NL","verf-diy",      "BE markt/DIY/BE Levis/BE TDS Levis"),
    ("BE","DIY","Xyla",       "NL","houtbeits",     "BE markt/DIY/BE Xyla/BE TDS Xyla"),
    ("BE","PROF","Herbol",    "DE","verf-prof",     "BE markt/PROF/BE Herbol/BE TDS Herbol"),
    ("BE","PROF","Sikkens",   "NL","verf-prof",     "BE markt/PROF/BE Sikkens/BE TDS Sikkens"),
    ("BE","PROF","Trimetal",  "NL","verf-prof",     "BE markt/PROF/BE Trimetal/BE TDS Trimetal"),
]

# ── Laad metadata CSV ─────────────────────────────────────────────────────────
def laad_metadata(csv_pad):
    meta = {}
    if not csv_pad.exists():
        print(f"⚠️  Metadata CSV niet gevonden: {csv_pad}")
        return meta
    with open(csv_pad, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            meta[row["bestandsnaam"]] = row
    print(f"✅ Metadata geladen: {len(meta)} bestanden")
    return meta

# ── Argument parser ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--reset", action="store_true", help="Wis alle bestaande records eerst")
parser.add_argument("--merk", help="Verwerk alleen dit merk (bijv. Sikkens)")
args = parser.parse_args()

# ── Reset optie ───────────────────────────────────────────────────────────────
if args.reset:
    print("🗑️  Bestaande records wissen...")
    supabase.table("documenten").delete().neq("id", 0).execute()
    print("✅ Tabel leeggemaakt")

# ── Model laden ───────────────────────────────────────────────────────────────
print("\n📦 Embedding model laden (all-MiniLM-L6-v2)...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Model klaar\n")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

metadata_lookup = laad_metadata(METADATA_CSV)

# ── Verwerking ────────────────────────────────────────────────────────────────
totaal_ok = 0
totaal_fout = 0
totaal_skip = 0

for markt, segment, merk, taal, categorie, relpad in MERKEN:
    if args.merk and merk.lower() != args.merk.lower():
        continue

    folder = BASE_DIR / relpad
    if not folder.exists():
        print(f"⚠️  Map niet gevonden: {relpad}")
        continue

    pdfs = sorted(folder.glob("*.pdf"))
    print(f"\n{'─'*50}")
    print(f"📂 {markt} {segment} {merk} — {len(pdfs)} bestanden")
    print(f"{'─'*50}")

    for pdf in pdfs:
        bestandsnaam = pdf.name

        # Controleer of al aanwezig in Supabase
        check = supabase.table("documenten").select("id").eq(
            "bestandsnaam", bestandsnaam
        ).limit(1).execute()
        if check.data:
            print(f"  ⏭️  {bestandsnaam} — al aanwezig, overgeslagen")
            totaal_skip += 1
            continue

        try:
            # PDF tekst uitlezen
            doc = fitz.open(str(pdf))
            tekst = "".join(pagina.get_text() for pagina in doc)
            doc.close()

            if len(tekst.strip()) < 50:
                print(f"  ⚠️  {bestandsnaam} — te weinig tekst (gescande PDF?)")
                totaal_skip += 1
                continue

            # Metadata ophalen
            m = metadata_lookup.get(bestandsnaam, {})
            product_naam = m.get("product", bestandsnaam.replace(".pdf",""))
            producttype  = m.get("producttype", "")
            toepassing   = m.get("toepassing", "")
            ondergrond   = m.get("ondergrond", "")
            basis        = m.get("basis", "")
            verfsysteem  = m.get("verfsysteem", "")
            datum        = m.get("datum", "")

            # Metadata prefix bij elk chunk (helpt bij zoeken)
            meta_prefix = (
                f"Merk: {merk} | Markt: {markt} | Segment: {segment} | "
                f"Product: {product_naam} | Categorie: {categorie} | "
                f"Toepassing: {toepassing} | Ondergrond: {ondergrond} | Basis: {basis}\n\n"
            )

            # Splitsen in chunks
            stukken = splitter.split_text(tekst)

            for stuk in stukken:
                volledige_tekst = meta_prefix + stuk
                embedding = model.encode(volledige_tekst).tolist()

                supabase.table("documenten").insert({
                    "bestandsnaam": bestandsnaam,
                    "product_naam": product_naam,
                    "markt":        markt,
                    "segment":      segment,
                    "merk":         merk,
                    "categorie":    categorie,
                    "producttype":  producttype,
                    "toepassing":   toepassing,
                    "ondergrond":   ondergrond,
                    "basis":        basis,
                    "verfsysteem":  verfsysteem,
                    "datum":        datum,
                    "inhoud":       stuk,
                    "embedding":    embedding,
                }).execute()

            print(f"  ✅ {product_naam} ({merk}) — {len(stukken)} chunks")
            totaal_ok += 1

        except Exception as e:
            print(f"  ❌ {bestandsnaam} — fout: {e}")
            totaal_fout += 1

# ── Samenvatting ──────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"✅ Succesvol: {totaal_ok} bestanden")
print(f"⏭️  Overgeslagen: {totaal_skip} (al aanwezig of te weinig tekst)")
print(f"❌ Fouten: {totaal_fout}")
print(f"{'='*50}")
