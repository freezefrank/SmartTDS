import os
import re
import json
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
    v = vraag.lower()
    if any(w in v for w in ["primer", "grondverf", "grondlaag", "voorstrijk", "hechtprimer"]):
        return "primer"
    if any(w in v for w in ["eindlaag", "aflak", "topcoat", "deklaag"]):
        return "eindlaag"
    if any(w in v for w in ["beits", "beitslaag"]):
        return "beits"
    if any(w in v for w in ["lak", "laklaag"]):
        return "lak"
    if any(w in v for w in ["vulmiddel", "plamuur", "vuller"]):
        return "vulmiddel"
    return None

def detecteer_ondergrond(vraag: str) -> str | None:
    v = vraag.lower()
    if any(w in v for w in ["metaal", "staal", "ijzer", "aluminium", "zink", "ferro"]):
        return "metaal"
    if any(w in v for w in ["hout", "houten", "hardhout", "zachthout"]):
        return "hout"
    if any(w in v for w in ["beton"]):
        return "beton"
    if any(w in v for w in ["steen", "metselwerk", "gevel"]):
        return "steen"
    if any(w in v for w in ["gips", "gipsplaat"]):
        return "gips"
    if any(w in v for w in ["kunststof", "plastic", "pvc"]):
        return "kunststof"
    return None

def parse_keuzevraag(tekst: str):
    """Haal keuzeblok uit Claude-respons. Geeft (schone_tekst, keuzedata) terug."""
    patroon = r'\[KEUZEVRAAG\](.*?)\[/KEUZEVRAAG\]'
    match = re.search(patroon, tekst, re.DOTALL)
    if not match:
        return tekst, None
    try:
        keuzedata = json.loads(match.group(1).strip())
        schone_tekst = tekst[:match.start()].strip()
        return schone_tekst, keuzedata
    except Exception:
        return tekst, None

# ── Pagina instellingen ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartTDS Verfassistent",
    page_icon="🎨",
    layout="wide"
)

# ── Sessie initialiseren ──────────────────────────────────────────────────────
if "berichten" not in st.session_state:
    st.session_state.berichten = []
if "pending_choices" not in st.session_state:
    st.session_state.pending_choices = None  # {"vraag": "...", "opties": [...]}
if "queued_message" not in st.session_state:
    st.session_state.queued_message = None

# ── Sidebar — Filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎨 SmartTDS")
    st.caption("Technische ondersteuning op basis van officiële datasheets")
    st.divider()

    st.subheader("🔍 Filters")

    markt_filter = st.selectbox("Markt", options=["Beide", "NL", "BE"], index=0)
    segment_filter = st.selectbox("Segment", options=["Beide", "PROF", "DIY"], index=0)

    merk_opties = [
        "Alle merken", "Sikkens", "Trimetal", "Flexa", "Dulux", "Levis",
        "Alabastine", "Cetabever", "Hammerite", "Herbol", "Glitsa", "Xyla", "Meesterhand"
    ]
    merk_filter = st.selectbox("Merk", options=merk_opties, index=0)

    producttype_opties = ["Automatisch", "Alle types", "primer", "grondverf",
                          "eindlaag", "lak", "beits", "vulmiddel", "coating"]
    producttype_filter = st.selectbox("Producttype", options=producttype_opties, index=0,
        help="'Automatisch' detecteert het type uit je vraag")

    ondergrond_opties = ["Automatisch", "Alle ondergronden",
                         "metaal", "hout", "beton", "steen", "muur", "gips", "kunststof"]
    ondergrond_filter = st.selectbox("Ondergrond", options=ondergrond_opties, index=0,
        help="'Automatisch' detecteert de ondergrond uit je vraag")

    st.divider()
    st.caption("💡 Tip: Stel vragen zoals:\n- 'Welke primer op staal buiten?'\n- 'Rubbol BL Azura droogtijd'\n- 'Verf bladert, wat nu?'")

    if st.button("🗑️ Gesprek wissen"):
        st.session_state.berichten = []
        st.session_state.pending_choices = None
        st.session_state.queued_message = None
        st.rerun()

# ── Hoofd interface ───────────────────────────────────────────────────────────
st.title("SmartTDS Verfassistent")
st.write("Stel een vraag over verfproducten en krijg een antwoord op basis van de officiële technische datasheets.")

# Berichtengeschiedenis tonen
for bericht in st.session_state.berichten:
    with st.chat_message(bericht["rol"]):
        st.markdown(bericht["tekst"])

# ── Keuzeknopjes tonen (verduidelijkingsvragen) ───────────────────────────────
if st.session_state.pending_choices:
    pc = st.session_state.pending_choices
    with st.chat_message("assistant"):
        st.markdown(f"**{pc['vraag']}**")
        opties = pc["opties"]
        # Max 4 per rij
        for rij_start in range(0, len(opties), 4):
            rij = opties[rij_start:rij_start + 4]
            cols = st.columns(len(rij))
            for i, optie in enumerate(rij):
                nummer = rij_start + i + 1
                if cols[i].button(f"{nummer}. {optie}", key=f"keuze_{rij_start}_{i}", use_container_width=True):
                    # Keuze opslaan als queued bericht
                    st.session_state.berichten.append({
                        "rol": "assistant",
                        "tekst": f"**{pc['vraag']}**"
                    })
                    st.session_state.pending_choices = None
                    st.session_state.queued_message = optie
                    st.rerun()

# ── Vraag ophalen (getypt of via knop) ───────────────────────────────────────
if st.session_state.queued_message:
    vraag = st.session_state.queued_message
    st.session_state.queued_message = None
else:
    vraag = st.chat_input("Stel je vraag...")

# ── Vraag verwerken ───────────────────────────────────────────────────────────
if vraag:
    st.session_state.berichten.append({"rol": "user", "tekst": vraag})
    with st.chat_message("user"):
        st.markdown(vraag)

    with st.chat_message("assistant"):
        with st.spinner("Zoeken in datasheets..."):

            # Automatische detectie
            auto_producttype = detecteer_producttype(vraag)
            auto_ondergrond  = detecteer_ondergrond(vraag)

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

            # Supabase RPC
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
                docs = supabase.rpc("zoek_documenten", {
                    "query_embedding": embedding,
                    "aantal": 12,
                    "filter_markt":   None if markt_filter == "Beide" else markt_filter,
                    "filter_segment": None if segment_filter == "Beide" else segment_filter,
                    "filter_merk":    None if merk_filter == "Alle merken" else merk_filter,
                }).execute().data or []

            # Context opbouwen
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

            # Filter-info
            filter_info = ""
            if markt_filter != "Beide": filter_info += f" Markt: {markt_filter}."
            if segment_filter != "Beide": filter_info += f" Segment: {segment_filter}."
            if merk_filter != "Alle merken": filter_info += f" Merk: {merk_filter}."
            if actief_producttype: filter_info += f" Producttype: {actief_producttype}."
            if actief_ondergrond: filter_info += f" Ondergrond: {actief_ondergrond}."

            # Gespreksgeschiedenis opbouwen voor Claude
            gesprek = []
            for b in st.session_state.berichten[:-1]:  # alles behalve huidige vraag
                rol = "user" if b["rol"] == "user" else "assistant"
                gesprek.append({"role": rol, "content": b["tekst"]})
            gesprek.append({"role": "user", "content": vraag})

            systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

STRIKTE REGELS:
- Beantwoord UITSLUITEND op basis van de meegeleverde TDS-context. Gebruik NOOIT algemene verfkennis.
- Als het antwoord NIET in de datasheets staat: "Geen TDS beschikbaar voor dit product."
- Let op [type: ...]: een [type: eindlaag] is GEEN primer, ook al noemt die TDS een primer.
- Noem altijd de exacte productnaam en het merk uit de context.
- Antwoord in het Nederlands. Bondig en praktisch.{filter_info}

VERDUIDELIJKINGSVRAGEN MET KEUZEMENU:
Als de vraag te weinig context heeft voor een goed antwoord, geef dan EERST een korte uitleg waarom je meer info nodig hebt.
Sluit daarna AF met een keuzeblok in dit exacte JSON-formaat:

[KEUZEVRAAG]{{"vraag": "Jouw vraag hier?", "opties": ["Optie 1", "Optie 2", "Optie 3"]}}[/KEUZEVRAAG]

Gebruik dit keuzeblok ALLEEN als je echt meer context nodig hebt. Maximaal 1 keuzeblok per reactie.
Voorbeeldvragen die een keuzemenu verdienen:
- Primervraag zonder ondergrondtype → {{"vraag": "Wat voor ondergrond?", "opties": ["Staal/ijzer (ferro)", "Aluminium/zink (non-ferro)", "Beide"]}}
- Primervraag zonder locatie → {{"vraag": "Binnen of buiten?", "opties": ["Buiten 🌤️", "Binnen 🏠", "Beide"]}}
- Houtvraag zonder detail → {{"vraag": "Welk houttype?", "opties": ["Nieuw hout", "Geschilderd hout", "Hardhout", "Zachthout"]}}
Stel GEEN vragen als de context al duidelijk is.

TDS-CONTEXT:
{context if context else "Geen relevante datasheets gevonden."}"""

            response = claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=800,
                system=systeem_prompt,
                messages=gesprek
            )

            ruwe_tekst = response.content[0].text
            schone_tekst, keuzedata = parse_keuzevraag(ruwe_tekst)

            # Antwoord tonen
            st.markdown(schone_tekst)

            # Keuzeknopjes instellen voor volgende render
            if keuzedata:
                st.session_state.pending_choices = keuzedata

            # Bronnen
            if bronnen:
                with st.expander(f"📄 Gebruikte bronnen ({len(bronnen)})"):
                    if auto_producttype or auto_ondergrond:
                        detectie = []
                        if auto_producttype: detectie.append(f"producttype → **{auto_producttype}**")
                        if auto_ondergrond: detectie.append(f"ondergrond → **{auto_ondergrond}**")
                        st.caption(f"🔍 Automatisch gedetecteerd: {', '.join(detectie)}")
                        st.divider()
                    for bron, score in bronnen:
                        st.caption(f"• {bron}  _(score: {score})_")

    # Sla antwoord op (zonder keuzeblok)
    st.session_state.berichten.append({"rol": "assistant", "tekst": schone_tekst})

    # Meteen rerun zodat keuzeknopjes verschijnen
    if keuzedata:
        st.rerun()
