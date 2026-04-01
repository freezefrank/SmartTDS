import os
import json
import fitz
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client
from sentence_transformers import SentenceTransformer

# Laad omgevingsvariabelen
load_dotenv("Supabase.env.local")

# Verbinding maken
supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
supabase_key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")
supabase = create_client(supabase_url, supabase_key)

# Lokaal AI model voor zoeken
print("AI model laden...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model klaar!")

# PDF splitter
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

pdf_dir = "alabastine_pdfs"
succesvol = 0
fouten = 0

print(f"\nPDF's verwerken uit map: {pdf_dir}")
print("-" * 40)

for pdf_bestand in os.listdir(pdf_dir):
    if not pdf_bestand.endswith(".pdf"):
        continue

    product_naam = pdf_bestand.replace(".pdf", "")
    pad = os.path.join(pdf_dir, pdf_bestand)

    print(f"\nVerwerken: {product_naam}")

    try:
        # PDF uitlezen
        doc = fitz.open(pad)
        tekst = "".join(pagina.get_text() for pagina in doc)
        doc.close()

        if len(tekst.strip()) < 50:
            print(f"  Overgeslagen - te weinig tekst")
            continue

        # Splitsen in stukken
        stukken = splitter.split_text(tekst)
        print(f"  {len(stukken)} tekstblokken gevonden")

        # Elk stuk opslaan in Supabase
        for i, stuk in enumerate(stukken):
            embedding = model.encode(stuk).tolist()

            supabase.table("documenten").insert({
                "product_naam": product_naam,
                "bestandsnaam": pdf_bestand,
                "inhoud": stuk,
                "embedding": embedding
            }).execute()

        print(f"  Opgeslagen in Supabase!")
        succesvol += 1

    except Exception as fout:
        print(f"  Fout: {fout}")
        fouten += 1

print("\n" + "=" * 40)
print(f"Klaar! {succesvol} PDF's succesvol verwerkt")
if fouten > 0:
    print(f"Let op: {fouten} PDF's mislukt")
print("=" * 40)