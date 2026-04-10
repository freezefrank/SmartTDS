import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
import anthropic

load_dotenv("Supabase.env.local")

supabase = create_client(
    os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
    os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")
)
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@st.cache_resource
def laad_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

model = laad_model()

# ── Pagina instellingen ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartTDS Verfassistent",
    page_icon="🎨",
    layout="wide"
)

# ── Sidebar — Filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎨 SmartTDS")
    st.caption("Technische ondersteuning op basis van officiële datasheets")
    st.divider()

    st.subheader("🔍 Filters")

    markt_filter = st.selectbox(
        "Markt",
        options=["Beide", "NL", "BE"],
        index=0,
        help="Selecteer de markt voor productspecifieke informatie"
    )

    segment_filter = st.selectbox(
        "Segment",
        options=["Beide", "PROF", "DIY"],
        index=0
    )

    merk_opties = [
        "Alle merken",
        "Sikkens", "Trimetal", "Flexa", "Dulux", "Levis",
        "Alabastine", "Cetabever", "Hammerite", "Herbol",
        "Glitsa", "Xyla", "Meesterhand"
    ]
    merk_filter = st.selectbox("Merk", options=merk_opties, index=0)

    producttype_opties = [
        "Alle types",
        "primer", "grondverf", "eindlaag", "lak", "beits",
        "vulmiddel", "coating", "reiniger", "verdunner"
    ]
    producttype_filter = st.selectbox(
        "Producttype",
        options=producttype_opties,
        index=0,
        help="Filter op type product — voorkomt dat eindlagen hoger scoren dan primers"
    )

    ondergrond_opties = [
        "Alle ondergronden",
        "metaal", "hout", "beton", "steen", "muur", "gips", "kunststof"
    ]
    ondergrond_filter = st.selectbox(
        "Ondergrond",
        options=ondergrond_opties,
        index=0,
        help="Filter op ondergrond (bijv. metaal → geeft alleen metaalprimers)"
    )

    st.divider()
    st.caption("💡 Tip: Stel vragen zoals:\n- 'Welke primer gebruik ik op nieuw hout buiten?'\n- 'Rubbol BL Azura droogtijd'\n- 'Verf bladert, wat nu?'")

    if st.button("🗑️ Gesprek wissen"):
        st.session_state.berichten = []
        st.rerun()

# ── Hoofd interface ───────────────────────────────────────────────────────────
st.title("SmartTDS Verfassistent")
st.write("Stel een vraag over verfproducten en krijg een antwoord op basis van de officiële technische datasheets.")

if "berichten" not in st.session_state:
    st.session_state.berichten = []

for bericht in st.session_state.berichten:
    with st.chat_message(bericht["rol"]):
        st.markdown(bericht["tekst"])

# ── Vraag verwerken ───────────────────────────────────────────────────────────
vraag = st.chat_input("Stel je vraag...")

if vraag:
    st.session_state.berichten.append({"rol": "user", "tekst": vraag})
    with st.chat_message("user"):
        st.markdown(vraag)

    with st.chat_message("assistant"):
        with st.spinner("Zoeken in datasheets..."):

            # Embedding van de vraag
            embedding = model.encode(vraag).tolist()

            # Supabase RPC aanroep met filters
            rpc_params = {
                "query_embedding":    embedding,
                "aantal":             12,
                "filter_markt":       None if markt_filter == "Beide" else markt_filter,
                "filter_segment":     None if segment_filter == "Beide" else segment_filter,
                "filter_merk":        None if merk_filter == "Alle merken" else merk_filter,
                "filter_producttype": None if producttype_filter == "Alle types" else producttype_filter,
                "filter_ondergrond":  None if ondergrond_filter == "Alle ondergronden" else ondergrond_filter,
            }

            try:
                resultaten = supabase.rpc("zoek_documenten", rpc_params).execute()
                docs = resultaten.data or []
            except Exception as e:
                # Fallback zonder extra filters als RPC parameters niet kloppen
                docs = supabase.rpc("zoek_documenten", {
                    "query_embedding": embedding,
                    "aantal": 12,
                    "filter_markt":   None if markt_filter == "Beide" else markt_filter,
                    "filter_segment": None if segment_filter == "Beide" else segment_filter,
                    "filter_merk":    None if merk_filter == "Alle merken" else merk_filter,
                }).execute().data or []

            if not docs:
                antwoord = (
                    "Geen TDS beschikbaar voor dit product of deze combinatie van filters. "
                    "Controleer de filters (markt, segment, merk, ondergrond) of stel de vraag anders."
                )
                st.markdown(antwoord)
            else:
                # Context opbouwen vanuit gevonden chunks
                context_stukken = []
                bronnen = []

                for r in docs:
                    product      = r.get("product_naam", "Onbekend")
                    merk_doc     = r.get("merk", "")
                    markt_doc    = r.get("markt", "")
                    segment_doc  = r.get("segment", "")
                    producttype_doc = r.get("producttype", "")
                    ondergrond_doc  = r.get("ondergrond", "")
                    inhoud       = r.get("inhoud", "")
                    bestand      = r.get("bestandsnaam", "")
                    similarity   = r.get("similarity", 0)

                    context_stukken.append(
                        f"[{merk_doc} — {product} | {markt_doc}/{segment_doc} | "
                        f"type: {producttype_doc} | ondergrond: {ondergrond_doc} | "
                        f"bestand: {bestand}]\n{inhoud}"
                    )

                    bron_label = f"{merk_doc} — {product} ({markt_doc}) · {bestand}"
                    if bron_label not in bronnen:
                        bronnen.append((bron_label, round(similarity, 3)))

                context = "\n\n---\n\n".join(context_stukken)

                # Actieve filters voor de prompt
                filter_info = ""
                if markt_filter != "Beide":
                    filter_info += f" Markt: {markt_filter}."
                if segment_filter != "Beide":
                    filter_info += f" Segment: {segment_filter}."
                if merk_filter != "Alle merken":
                    filter_info += f" Merk: {merk_filter}."
                if producttype_filter != "Alle types":
                    filter_info += f" Producttype: {producttype_filter}."
                if ondergrond_filter != "Alle ondergronden":
                    filter_info += f" Ondergrond: {ondergrond_filter}."

                systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

STRIKTE REGELS:
- Beantwoord UITSLUITEND op basis van de meegeleverde TDS-context hieronder. Gebruik NOOIT algemene verfkennis.
- Als het antwoord NIET in de meegeleverde datasheets staat, zeg dan letterlijk: "Deze informatie staat niet in de beschikbare datasheets."
- Verwijs nooit naar producten die niet in de context staan.
- Let op het documenttype in de context: een [type: eindlaag] is GEEN primer, ook al noemt het datasheet een primer als aanbevolen grondlaag.
- Noem altijd de exacte productnaam en het merk zoals vermeld in de context.
- Als er NL én BE versies beschikbaar zijn voor hetzelfde product, benoem dan het verschil.
- Antwoord altijd in het Nederlands.
- Wees bondig en praktisch — de medewerker heeft een klant aan de lijn.{filter_info}

TDS-CONTEXT (alleen deze bronnen gebruiken):
{context}"""

                response = claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=800,
                    system=systeem_prompt,
                    messages=[{"role": "user", "content": vraag}]
                )

                antwoord = response.content[0].text

                # Antwoord tonen
                st.markdown(antwoord)

                # Bronnen tonen met similarity score
                if bronnen:
                    with st.expander(f"📄 Gebruikte bronnen ({len(bronnen)})"):
                        for bron, score in bronnen:
                            st.caption(f"• {bron}  _(score: {score})_")

        st.session_state.berichten.append({"rol": "assistant", "tekst": antwoord})
