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

# ── Slimme trefwoorddetectie ──────────────────────────────────────────────────
def detecteer_producttype(vraag: str) -> str | None:
    """Detecteer automatisch producttype uit de vraag."""
    v = vraag.lower()
    if any(w in v for w in ["primer", "grondverf", "grondlaag", "voorstrijk", "hechtprimer", "hechting"]):
        return "primer"
    if any(w in v for w in ["eindlaag", "aflak", "topcoat", "afwerklaag", "deklaag"]):
        return "eindlaag"
    if any(w in v for w in ["beits", "beitslaag"]):
        return "beits"
    if any(w in v for w in ["lak", "laklaag", "vernislaag"]):
        return "lak"
    if any(w in v for w in ["vulmiddel", "plamuur", "vuller", "zetplamuur"]):
        return "vulmiddel"
    return None

def detecteer_ondergrond(vraag: str) -> str | None:
    """Detecteer automatisch ondergrond uit de vraag."""
    v = vraag.lower()
    if any(w in v for w in ["metaal", "staal", "ijzer", "aluminium", "zink", "ferro", "non-ferro"]):
        return "metaal"
    if any(w in v for w in ["hout", "houten", "timmerhout", "hardhout", "zachthout"]):
        return "hout"
    if any(w in v for w in ["beton", "betonnen"]):
        return "beton"
    if any(w in v for w in ["steen", "stenen", "metselwerk", "gevel"]):
        return "steen"
    if any(w in v for w in ["gips", "gipsplaat", "gipskarton"]):
        return "gips"
    if any(w in v for w in ["kunststof", "plastic", "pvc", "upvc"]):
        return "kunststof"
    return None

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
        "Automatisch", "Alle types",
        "primer", "grondverf", "eindlaag", "lak", "beits",
        "vulmiddel", "coating", "reiniger", "verdunner"
    ]
    producttype_filter = st.selectbox(
        "Producttype",
        options=producttype_opties,
        index=0,
        help="'Automatisch' detecteert het type uit je vraag. Voorkomt dat eindlagen boven primers scoren."
    )

    ondergrond_opties = [
        "Automatisch", "Alle ondergronden",
        "metaal", "hout", "beton", "steen", "muur", "gips", "kunststof"
    ]
    ondergrond_filter = st.selectbox(
        "Ondergrond",
        options=ondergrond_opties,
        index=0,
        help="'Automatisch' detecteert de ondergrond uit je vraag."
    )

    st.divider()
    st.caption("💡 Tip: Stel vragen zoals:\n- 'Welke primer gebruik ik op staal buiten?'\n- 'Rubbol BL Azura droogtijd'\n- 'Verf bladert, wat nu?'")

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

            # ── Automatische detectie ─────────────────────────────────────────
            auto_producttype = detecteer_producttype(vraag)
            auto_ondergrond  = detecteer_ondergrond(vraag)

            # Handmatige filter wint van automatisch (tenzij op "Automatisch")
            if producttype_filter == "Automatisch":
                actief_producttype = auto_producttype
            elif producttype_filter == "Alle types":
                actief_producttype = None
            else:
                actief_producttype = producttype_filter

            if ondergrond_filter == "Automatisch":
                actief_ondergrond = auto_ondergrond
            elif ondergrond_filter == "Alle ondergronden":
                actief_ondergrond = None
            else:
                actief_ondergrond = ondergrond_filter

            # ── Embedding + Supabase RPC ──────────────────────────────────────
            embedding = model.encode(vraag).tolist()

            rpc_params = {
                "query_embedding":    embedding,
                "aantal":             12,
                "filter_markt":       None if markt_filter == "Beide" else markt_filter,
                "filter_segment":     None if segment_filter == "Beide" else segment_filter,
                "filter_merk":        None if merk_filter == "Alle merken" else merk_filter,
                "filter_producttype": actief_producttype,
                "filter_ondergrond":  actief_ondergrond,
            }

            try:
                resultaten = supabase.rpc("zoek_documenten", rpc_params).execute()
                docs = resultaten.data or []
            except Exception:
                # Fallback: alleen markt/segment/merk filters
                docs = supabase.rpc("zoek_documenten", {
                    "query_embedding": embedding,
                    "aantal": 12,
                    "filter_markt":   None if markt_filter == "Beide" else markt_filter,
                    "filter_segment": None if segment_filter == "Beide" else segment_filter,
                    "filter_merk":    None if merk_filter == "Alle merken" else merk_filter,
                }).execute().data or []

            # ── Context opbouwen ──────────────────────────────────────────────
            context_stukken = []
            bronnen = []

            for r in (docs or []):
                product         = r.get("product_naam", "Onbekend")
                merk_doc        = r.get("merk", "")
                markt_doc       = r.get("markt", "")
                segment_doc     = r.get("segment", "")
                producttype_doc = r.get("producttype", "")
                ondergrond_doc  = r.get("ondergrond", "")
                inhoud          = r.get("inhoud", "")
                bestand         = r.get("bestandsnaam", "")
                similarity      = r.get("similarity", 0)

                context_stukken.append(
                    f"[{merk_doc} — {product} | {markt_doc}/{segment_doc} | "
                    f"type: {producttype_doc} | ondergrond: {ondergrond_doc} | "
                    f"bestand: {bestand}]\n{inhoud}"
                )

                bron_label = f"{merk_doc} — {product} ({markt_doc}) · {bestand}"
                if bron_label not in [b for b, _ in bronnen]:
                    bronnen.append((bron_label, round(similarity, 3)))

            context = "\n\n---\n\n".join(context_stukken) if context_stukken else ""

            # ── Filter-info voor de prompt ─────────────────────────────────────
            filter_info = ""
            if markt_filter != "Beide":
                filter_info += f" Markt: {markt_filter}."
            if segment_filter != "Beide":
                filter_info += f" Segment: {segment_filter}."
            if merk_filter != "Alle merken":
                filter_info += f" Merk: {merk_filter}."
            if actief_producttype:
                filter_info += f" Producttype: {actief_producttype} (automatisch gedetecteerd)."
            if actief_ondergrond:
                filter_info += f" Ondergrond: {actief_ondergrond} (automatisch gedetecteerd)."

            # ── System prompt ──────────────────────────────────────────────────
            systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

STRIKTE REGELS:
- Beantwoord UITSLUITEND op basis van de meegeleverde TDS-context hieronder. Gebruik NOOIT algemene verfkennis.
- Als het antwoord NIET in de meegeleverde datasheets staat, zeg dan letterlijk: "Geen TDS beschikbaar voor dit product."
- Let op het veld [type: ...] in de context. Een [type: eindlaag] is GEEN primer, ook al noemt die TDS een primer als aanbevolen grondlaag. Geef bij vragen over primers alleen producten waarvan [type: primer] of [type: grondverf] in de context staat.
- Verwijs nooit naar producten die niet in de context staan.
- Noem altijd de exacte productnaam en het merk zoals vermeld in de context.
- Als er NL én BE versies beschikbaar zijn voor hetzelfde product, benoem dan het verschil.
- Antwoord altijd in het Nederlands.
- Wees bondig en praktisch — de medewerker heeft een klant aan de lijn.{filter_info}

VERDUIDELIJKINGSVRAGEN:
Als de vraag te weinig context heeft om een goed advies te geven, stel dan MAXIMAAL 2 gerichte vragen VOORDAT je een productadvies geeft. Gebruik dit alleen als het echt nodig is. Voorbeelden van wanneer je vragen stelt:
- Bij een primervraag: is de ondergrond ferro (staal/ijzer) of non-ferro (aluminium/zink)? Binnen of buiten?
- Bij een houtbeitsvraag: gaat het om nieuw hout of geschilderd hout? Buiten of binnen?
- Bij een plafond-/muurvraag: nieuwbouw of renovatie? Welk merk heeft de voorkeur?
Stel GEEN vragen als de context al duidelijk genoeg is. Stel nooit meer dan 2 vragen tegelijk.

TDS-CONTEXT (alleen deze bronnen gebruiken):
{context if context else "Geen relevante datasheets gevonden voor deze zoekcombinatie."}"""

            # ── Claude aanroep ─────────────────────────────────────────────────
            response = claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                system=systeem_prompt,
                messages=[{"role": "user", "content": vraag}]
            )

            antwoord = response.content[0].text
            st.markdown(antwoord)

            # ── Bronnen + detectie-info ────────────────────────────────────────
            with st.expander(f"📄 Gebruikte bronnen ({len(bronnen)})"):
                if auto_producttype or auto_ondergrond:
                    detectie_info = []
                    if auto_producttype:
                        detectie_info.append(f"producttype → **{auto_producttype}**")
                    if auto_ondergrond:
                        detectie_info.append(f"ondergrond → **{auto_ondergrond}**")
                    st.caption(f"🔍 Automatisch gedetecteerd: {', '.join(detectie_info)}")
                    st.divider()
                for bron, score in bronnen:
                    st.caption(f"• {bron}  _(score: {score})_")

    st.session_state.berichten.append({"rol": "assistant", "tekst": antwoord})
