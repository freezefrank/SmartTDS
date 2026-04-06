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

    st.divider()
    st.caption("💡 Tip: Stel vragen zoals:\n- 'Welke primer gebruik ik op nieuw hout buiten?'\n- 'Rubbol Bl Azura droogtijd'\n- 'Verf bladert, wat nu?'")

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
                "query_embedding": embedding,
                "aantal": 6,
                "filter_markt":    None if markt_filter == "Beide" else markt_filter,
                "filter_segment":  None if segment_filter == "Beide" else segment_filter,
                "filter_merk":     None if merk_filter == "Alle merken" else merk_filter,
            }

            try:
                resultaten = supabase.rpc("zoek_documenten", rpc_params).execute()
                docs = resultaten.data or []
            except Exception as e:
                # Fallback zonder filters als RPC parameters niet kloppen
                docs = supabase.rpc("zoek_documenten", {
                    "query_embedding": embedding,
                    "aantal": 6
                }).execute().data or []

            if not docs:
                antwoord = (
                    "Ik kon geen relevante informatie vinden in de datasheets voor deze vraag. "
                    "Probeer een specifiekere productnaam of pas de filters aan."
                )
                st.markdown(antwoord)
            else:
                # Context opbouwen vanuit gevonden chunks
                context_stukken = []
                bronnen = []

                for r in docs:
                    product  = r.get("product_naam", "Onbekend")
                    merk_doc = r.get("merk", "")
                    markt_doc= r.get("markt", "")
                    inhoud   = r.get("inhoud", "")
                    bestand  = r.get("bestandsnaam", "")

                    context_stukken.append(
                        f"[{merk_doc} — {product} ({markt_doc})]\n{inhoud}"
                    )

                    bron_label = f"{merk_doc} — {product} ({markt_doc})"
                    if bron_label not in bronnen:
                        bronnen.append(bron_label)

                context = "\n\n---\n\n".join(context_stukken)

                # Actieve filters voor de prompt
                filter_info = ""
                if markt_filter != "Beide":
                    filter_info += f" Markt: {markt_filter}."
                if segment_filter != "Beide":
                    filter_info += f" Segment: {segment_filter}."
                if merk_filter != "Alle merken":
                    filter_info += f" Merk: {merk_filter}."

                systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

REGELS:
- Beantwoord uitsluitend op basis van de meegeleverde productinformatie uit de technische datasheets.
- Gebruik GEEN algemene verfkennis die niet in de datasheets staat.
- Als de informatie niet in de datasheets staat, zeg dat dan eerlijk.
- Geef praktische, concrete antwoorden — de medewerker heeft een klant aan de lijn.
- Noem altijd het exacte productmerk en de productnaam.
- Als er een verschil is tussen NL en BE versies, benoem dat.
- Antwoord altijd in het Nederlands.
- Wees bondig: maximaal 5 zinnen tenzij de vraag om meer detail vraagt.{filter_info}

PRODUCTINFORMATIE UIT DATASHEETS:
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

                # Bronnen tonen
                if bronnen:
                    with st.expander(f"📄 Gebruikte bronnen ({len(bronnen)})"):
                        for bron in bronnen:
                            st.caption(f"• {bron}")

        st.session_state.berichten.append({"rol": "assistant", "tekst": antwoord})
