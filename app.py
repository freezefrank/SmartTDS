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

# ── Trefwoorddetectie ─────────────────────────────────────────────────────────
def detecteer_producttype(tekst: str) -> str | None:
    t = tekst.lower()
    if any(w in t for w in ["primer", "grondverf", "grondlaag", "voorstrijk", "hechtprimer"]):
        return "primer"
    if any(w in t for w in ["eindlaag", "aflak", "topcoat", "deklaag"]):
        return "eindlaag"
    if any(w in t for w in ["beits"]):
        return "beits"
    if any(w in t for w in ["lak", "laklaag"]):
        return "lak"
    if any(w in t for w in ["vulmiddel", "plamuur", "vuller"]):
        return "vulmiddel"
    return None

def detecteer_ondergrond(tekst: str) -> str | None:
    t = tekst.lower()
    if any(w in t for w in ["metaal", "staal", "ijzer", "ferro", "aluminium", "zink", "non-ferro"]):
        return "metaal"
    if any(w in t for w in ["hout", "houten", "hardhout", "zachthout"]):
        return "hout"
    if any(w in t for w in ["beton"]):
        return "beton"
    if any(w in t for w in ["steen", "metselwerk", "gevel"]):
        return "steen"
    if any(w in t for w in ["gips", "gipsplaat"]):
        return "gips"
    if any(w in t for w in ["kunststof", "plastic", "pvc"]):
        return "kunststof"
    return None

def detecteer_locatie(tekst: str) -> str | None:
    t = tekst.lower()
    if "buiten" in t or "exterieur" in t:
        return "buiten"
    if "binnen" in t or "interieur" in t:
        return "binnen"
    return None

def detecteer_metaaltype(tekst: str) -> str | None:
    t = tekst.lower()
    if any(w in t for w in ["staal", "ijzer", "ferro"]) and "non-ferro" not in t:
        return "ferro"
    if any(w in t for w in ["aluminium", "zink", "non-ferro", "nonferro"]):
        return "non-ferro"
    return None

def detecteer_markt(tekst: str) -> str | None:
    t = tekst.lower()
    if any(w in t for w in ["nederland", "nl ", "nl-", "nederlandse"]):
        return "NL"
    if any(w in t for w in ["belgië", "belgie", "be ", "belgische", "belgisch"]):
        return "BE"
    return None

def detecteer_segment(tekst: str) -> str | None:
    t = tekst.lower()
    if any(w in t for w in ["professioneel", "prof ", "schilder", "vakman", "aannemer"]):
        return "PROF"
    if any(w in t for w in ["particulier", "diy", "doe-het-zelf", "consument"]):
        return "DIY"
    return None

BEKENDE_MERKEN = [
    "sikkens", "trimetal", "flexa", "dulux", "levis",
    "alabastine", "cetabever", "hammerite", "herbol", "glitsa", "xyla", "meesterhand"
]

def detecteer_merk(tekst: str) -> str | None:
    t = tekst.lower()
    for merk in BEKENDE_MERKEN:
        if merk in t:
            return merk.capitalize()
    return None

# Merken per markt/segment combinatie
MERKEN_NL_PROF = ["Sikkens", "Trimetal", "Herbol", "Meesterhand"]
MERKEN_NL_DIY  = ["Alabastine", "Cetabever", "Flexa", "Glitsa", "Hammerite"]
MERKEN_BE_PROF = ["Sikkens", "Trimetal", "Herbol"]
MERKEN_BE_DIY  = ["Dulux", "Hammerite", "Levis", "Xyla"]

def merken_voor_context(markt: str, segment: str, antwoorden: dict) -> list:
    """Geeft de beschikbare merken terug op basis van actieve markt en segment."""
    # Bepaal actieve markt en segment (sidebar óf antwoorden)
    act_markt   = markt
    act_segment = segment

    if act_markt == "Beide" and "markt" in antwoorden:
        if "NL" in antwoorden["markt"] or "Nederland" in antwoorden["markt"]:
            act_markt = "NL"
        elif "BE" in antwoorden["markt"] or "België" in antwoorden["markt"]:
            act_markt = "BE"

    if act_segment == "Beide" and "segment" in antwoorden:
        if "PROF" in antwoorden["segment"] or "Professioneel" in antwoorden["segment"]:
            act_segment = "PROF"
        elif "DIY" in antwoorden["segment"] or "Particulier" in antwoorden["segment"]:
            act_segment = "DIY"

    # Stel merklijst samen
    if act_markt == "NL" and act_segment == "PROF": return MERKEN_NL_PROF
    if act_markt == "NL" and act_segment == "DIY":  return MERKEN_NL_DIY
    if act_markt == "BE" and act_segment == "PROF": return MERKEN_BE_PROF
    if act_markt == "BE" and act_segment == "DIY":  return MERKEN_BE_DIY
    if act_markt == "NL": return MERKEN_NL_PROF + MERKEN_NL_DIY
    if act_markt == "BE": return MERKEN_BE_PROF + MERKEN_BE_DIY
    if act_segment == "PROF": return list(dict.fromkeys(MERKEN_NL_PROF + MERKEN_BE_PROF))
    if act_segment == "DIY":  return list(dict.fromkeys(MERKEN_NL_DIY  + MERKEN_BE_DIY))
    return list(dict.fromkeys(MERKEN_NL_PROF + MERKEN_NL_DIY + MERKEN_BE_PROF + MERKEN_BE_DIY))

EINDLAAG_TYPES = {"eindlaag", "aflak", "topcoat", "deklaag", "afwerklak", "coating"}

def filter_eindlagen(docs: list, gevraagd_producttype: str | None) -> list:
    """Verwijder eindlagen uit resultaten als er om een primer gevraagd wordt."""
    if gevraagd_producttype not in ("primer", "grondverf"):
        return docs
    gefilterd = []
    for doc in docs:
        ptype = (doc.get("producttype") or "").lower()
        # Behoud als producttype niet duidelijk een eindlaag is
        if not any(e in ptype for e in EINDLAAG_TYPES):
            gefilterd.append(doc)
    # Als alles weggevallen is, geef origineel terug (beter iets dan niets)
    return gefilterd if gefilterd else docs

# ── Vervolgvragen bepalen (voor Claude-call) ──────────────────────────────────
def bepaal_vervolgvragen(vraag: str, antwoorden: dict,
                          markt_filter: str, segment_filter: str, merk_filter: str) -> dict | None:
    """Geeft de eerstvolgende benodigde vervolgvraag terug, of None als genoeg context."""
    alles = vraag + " " + " ".join(antwoorden.values())
    producttype = detecteer_producttype(alles)
    ondergrond  = detecteer_ondergrond(alles)
    locatie     = detecteer_locatie(alles)
    metaaltype  = detecteer_metaaltype(alles)
    markt       = detecteer_markt(alles)
    segment     = detecteer_segment(alles)
    merk        = detecteer_merk(alles)

    # 1. Markt / land — als sidebar op "Beide" staat en niet duidelijk uit vraag
    if markt_filter == "Beide" and not markt and "markt" not in antwoorden:
        return {
            "key": "markt",
            "vraag": "Voor welke markt / welk land?",
            "opties": ["🇳🇱 Nederland (NL)", "🇧🇪 België (BE)", "Beide landen"]
        }

    # 2. Segment — als sidebar op "Beide" staat
    if segment_filter == "Beide" and not segment and "segment" not in antwoorden:
        return {
            "key": "segment",
            "vraag": "Voor professioneel gebruik of particulier?",
            "opties": ["🔧 Professioneel / schilder (PROF)", "🏠 Particulier / DIY", "Beide"]
        }

    # 3. Primer zonder ondergrond
    if producttype in ("primer", "grondverf") and not ondergrond:
        return {
            "key": "ondergrond",
            "vraag": "Wat voor ondergrond?",
            "opties": ["Staal/ijzer (ferro) 🔩", "Aluminium/zink (non-ferro) ✨",
                       "Hout 🪵", "Beton/steen 🧱", "Gips/muur 🏠", "Kunststof 🔵"]
        }

    # 4. Metaalprimer: ferro of non-ferro?
    if producttype in ("primer", "grondverf") and ondergrond == "metaal" and not metaaltype:
        return {
            "key": "metaaltype",
            "vraag": "Ferro of non-ferro metaal?",
            "opties": ["Staal/ijzer (ferro) 🔩", "Aluminium/zink (non-ferro) ✨", "Beide / weet ik niet"]
        }

    # 5. Primer/beits/lak zonder buiten/binnen
    if producttype in ("primer", "eindlaag", "beits", "lak") and not locatie:
        return {
            "key": "locatie",
            "vraag": "Binnen of buiten?",
            "opties": ["Buiten 🌤️", "Binnen 🏠", "Beide"]
        }

    # 6. Hout zonder locatie
    if ondergrond == "hout" and not locatie:
        return {
            "key": "locatie",
            "vraag": "Binnen of buiten?",
            "opties": ["Buiten 🌤️", "Binnen 🏠", "Beide"]
        }

    # 7. Merkvoorkeur — gefilterd op actieve markt/segment
    if merk_filter == "Alle merken" and not merk and "merk" not in antwoorden:
        beschikbare_merken = merken_voor_context(markt_filter, segment_filter, antwoorden)
        return {
            "key": "merk",
            "vraag": "Is er een merkvoorkeur?",
            "opties": beschikbare_merken + ["Geen voorkeur"]
        }

    return None  # Genoeg context, ga naar Claude

# ── Pagina instellingen ───────────────────────────────────────────────────────
st.set_page_config(page_title="SmartTDS Verfassistent", page_icon="🎨", layout="wide")

# ── Sessie initialiseren ──────────────────────────────────────────────────────
defaults = {
    "berichten": [],
    "pending_vraag": None,   # {"key", "vraag", "opties"}
    "antwoorden": {},        # {"ondergrond": "Staal/ijzer", "locatie": "Buiten", ...}
    "originele_vraag": None, # De originele gebruikersvraag
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎨 SmartTDS")
    st.caption("Technische ondersteuning op basis van officiële datasheets")
    st.divider()
    st.subheader("🔍 Filters")

    markt_filter    = st.selectbox("Markt", ["Beide", "NL", "BE"], index=0)
    segment_filter  = st.selectbox("Segment", ["Beide", "PROF", "DIY"], index=0)
    merk_opties     = ["Alle merken", "Sikkens", "Trimetal", "Flexa", "Dulux", "Levis",
                       "Alabastine", "Cetabever", "Hammerite", "Herbol", "Glitsa", "Xyla", "Meesterhand"]
    merk_filter     = st.selectbox("Merk", merk_opties, index=0)
    producttype_opties = ["Automatisch", "Alle types", "primer", "grondverf",
                          "eindlaag", "lak", "beits", "vulmiddel", "coating"]
    producttype_filter = st.selectbox("Producttype", producttype_opties, index=0,
                                      help="'Automatisch' detecteert het type uit je vraag")
    ondergrond_opties  = ["Automatisch", "Alle ondergronden",
                          "metaal", "hout", "beton", "steen", "muur", "gips", "kunststof"]
    ondergrond_filter  = st.selectbox("Ondergrond", ondergrond_opties, index=0,
                                      help="'Automatisch' detecteert de ondergrond uit je vraag")
    st.divider()
    st.caption("💡 Tip:\n- 'Welke primer op staal buiten?'\n- 'Rubbol BL Azura droogtijd'\n- 'Verf bladert, wat nu?'")

    if st.button("🗑️ Gesprek wissen"):
        for k in ["berichten", "pending_vraag", "antwoorden", "originele_vraag"]:
            st.session_state[k] = [] if k == "berichten" else {} if k == "antwoorden" else None
        st.rerun()

# ── Hoofd interface ───────────────────────────────────────────────────────────
st.title("SmartTDS Verfassistent")
st.write("Stel een vraag over verfproducten en krijg een antwoord op basis van de officiële technische datasheets.")

# Gespreksgeschiedenis tonen
for bericht in st.session_state.berichten:
    with st.chat_message(bericht["rol"]):
        st.markdown(bericht["tekst"])

# ── Keuzeknopjes tonen ────────────────────────────────────────────────────────
if st.session_state.pending_vraag:
    pv = st.session_state.pending_vraag
    with st.chat_message("assistant"):
        st.markdown(f"**{pv['vraag']}**")
        opties = pv["opties"]
        for rij_start in range(0, len(opties), 4):
            rij  = opties[rij_start:rij_start + 4]
            cols = st.columns(len(rij))
            for i, optie in enumerate(rij):
                nummer = rij_start + i + 1
                if cols[i].button(f"{nummer}. {optie}", key=f"keuze_{rij_start}_{i}",
                                   use_container_width=True):
                    # Sla antwoord op in berichten + antwoorden
                    st.session_state.berichten.append({
                        "rol": "assistant",
                        "tekst": f"**{pv['vraag']}**"
                    })
                    st.session_state.berichten.append({"rol": "user", "tekst": optie})
                    st.session_state.antwoorden[pv["key"]] = optie
                    st.session_state.pending_vraag = None
                    st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
vraag_input = st.chat_input("Stel je vraag...",
                             disabled=st.session_state.pending_vraag is not None)

# ── Verwerk nieuwe vraag of doorgaan na keuze ─────────────────────────────────
verwerk_nu = False
if vraag_input:
    # Nieuwe vraag: reset context
    st.session_state.originele_vraag = vraag_input
    st.session_state.antwoorden      = {}
    st.session_state.pending_vraag   = None
    st.session_state.berichten.append({"rol": "user", "tekst": vraag_input})
    with st.chat_message("user"):
        st.markdown(vraag_input)
    verwerk_nu = True

elif (st.session_state.originele_vraag
      and not st.session_state.pending_vraag
      and st.session_state.antwoorden):
    # Gebruiker heeft een keuze gemaakt — check of meer vragen nodig zijn
    verwerk_nu = True

if verwerk_nu and st.session_state.originele_vraag:
    originele = st.session_state.originele_vraag
    antwoorden = st.session_state.antwoorden

    # Volgende vervolgvraag nodig?
    volgende = bepaal_vervolgvragen(originele, antwoorden,
                                    markt_filter, segment_filter, merk_filter)

    if volgende:
        # Sla vervolgvraag op en toon knoppen bij volgende render
        st.session_state.pending_vraag = volgende
        st.rerun()
    else:
        # Genoeg context — bouw verrijkte vraag en roep Claude aan
        verrijkte_vraag = originele
        if antwoorden:
            extra = ", ".join(f"{k}: {v}" for k, v in antwoorden.items())
            verrijkte_vraag += f" ({extra})"

        with st.chat_message("assistant"):
            with st.spinner("Zoeken in datasheets..."):

                # Detectie op basis van volledige context (inclusief antwoorden)
                alles = verrijkte_vraag
                auto_producttype = detecteer_producttype(alles)
                auto_ondergrond  = detecteer_ondergrond(alles)

                # Markt uit antwoorden of sidebar
                actief_markt = None
                if markt_filter != "Beide":
                    actief_markt = markt_filter
                elif "markt" in antwoorden:
                    if "NL" in antwoorden["markt"] or "Nederland" in antwoorden["markt"]:
                        actief_markt = "NL"
                    elif "BE" in antwoorden["markt"] or "België" in antwoorden["markt"]:
                        actief_markt = "BE"

                # Segment uit antwoorden of sidebar
                actief_segment = None
                if segment_filter != "Beide":
                    actief_segment = segment_filter
                elif "segment" in antwoorden:
                    if "PROF" in antwoorden["segment"] or "Professioneel" in antwoorden["segment"]:
                        actief_segment = "PROF"
                    elif "DIY" in antwoorden["segment"] or "Particulier" in antwoorden["segment"]:
                        actief_segment = "DIY"

                # Merk uit antwoorden of sidebar
                actief_merk = None
                if merk_filter != "Alle merken":
                    actief_merk = merk_filter
                elif "merk" in antwoorden and antwoorden["merk"] != "Geen voorkeur":
                    actief_merk = antwoorden["merk"]

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

                # Query-tekst opschonen voor full-text search
                # Stopwoorden verwijderen zodat alleen inhoudelijke woorden overblijven
                stopwoorden = {"ik", "een", "de", "het", "voor", "op", "in", "aan",
                               "zoek", "wil", "wat", "welke", "is", "zijn", "heb",
                               "van", "met", "te", "dat", "die", "ze", "bij"}
                woorden = [w for w in verrijkte_vraag.lower().split()
                           if w.isalpha() and w not in stopwoorden and len(w) > 2]
                query_tekst = " ".join(woorden) if woorden else None

                # Supabase RPC — hybrid search
                embedding  = model.encode(verrijkte_vraag).tolist()
                rpc_params = {
                    "query_embedding":    embedding,
                    "query_tekst":        query_tekst,
                    "aantal":             12,
                    "rrf_k":              60,
                    "filter_markt":       actief_markt,
                    "filter_segment":     actief_segment,
                    "filter_merk":        actief_merk,
                    "filter_producttype": actief_producttype,
                    "filter_ondergrond":  actief_ondergrond,
                }

                try:
                    docs = supabase.rpc("zoek_documenten", rpc_params).execute().data or []
                except Exception:
                    docs = []

                # Fallback 1: zonder producttype-filter
                if not docs and actief_producttype:
                    try:
                        rpc2 = {**rpc_params, "filter_producttype": None}
                        docs = supabase.rpc("zoek_documenten", rpc2).execute().data or []
                    except Exception:
                        docs = []

                # Fallback 2: zonder ondergrond-filter
                if not docs and actief_ondergrond:
                    try:
                        rpc3 = {**rpc_params, "filter_producttype": None, "filter_ondergrond": None}
                        docs = supabase.rpc("zoek_documenten", rpc3).execute().data or []
                    except Exception:
                        docs = []

                # Post-filter: verwijder eindlagen als er om een primer gevraagd wordt
                docs = filter_eindlagen(docs, auto_producttype)

                # Context opbouwen
                context_stukken, bronnen = [], []
                for r in docs:
                    product  = r.get("product_naam", "Onbekend")
                    merk_doc = r.get("merk", "")
                    markt_doc= r.get("markt", "")
                    seg_doc  = r.get("segment", "")
                    ptype    = r.get("producttype", "")
                    ond      = r.get("ondergrond", "")
                    inhoud   = r.get("inhoud", "")
                    bestand  = r.get("bestandsnaam", "")
                    score    = round(r.get("similarity", 0), 3)

                    context_stukken.append(
                        f"[{merk_doc} — {product} | {markt_doc}/{seg_doc} | "
                        f"type: {ptype} | ondergrond: {ond} | bestand: {bestand}]\n{inhoud}"
                    )
                    label = f"{merk_doc} — {product} ({markt_doc}) · {bestand}"
                    if label not in [b for b, _ in bronnen]:
                        bronnen.append((label, score))

                context = "\n\n---\n\n".join(context_stukken) if context_stukken else ""

                filter_info = ""
                if markt_filter != "Beide":       filter_info += f" Markt: {markt_filter}."
                if segment_filter != "Beide":     filter_info += f" Segment: {segment_filter}."
                if merk_filter != "Alle merken":  filter_info += f" Merk: {merk_filter}."
                if actief_producttype:            filter_info += f" Producttype: {actief_producttype}."
                if actief_ondergrond:             filter_info += f" Ondergrond: {actief_ondergrond}."

                # Gespreksgeschiedenis voor Claude
                gesprek = []
                for b in st.session_state.berichten:
                    rol = "user" if b["rol"] == "user" else "assistant"
                    gesprek.append({"role": rol, "content": b["tekst"]})
                # Vervang laatste user bericht door verrijkte versie
                if gesprek and gesprek[-1]["role"] == "user":
                    gesprek[-1]["content"] = verrijkte_vraag
                else:
                    gesprek.append({"role": "user", "content": verrijkte_vraag})

                systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

STRIKTE REGELS:
- Beantwoord UITSLUITEND op basis van de meegeleverde TDS-context. Gebruik NOOIT algemene verfkennis.
- Als het antwoord NIET in de datasheets staat: zeg "Geen TDS beschikbaar voor dit product."
- Let op [type: ...]: een [type: eindlaag] is GEEN primer, ook al noemt die TDS een primer.
- Noem altijd de exacte productnaam en het merk uit de context.
- Antwoord in het Nederlands. Bondig en praktisch — medewerker heeft klant aan de lijn.{filter_info}

TDS-CONTEXT (alleen deze bronnen gebruiken):
{context if context else "Geen relevante datasheets gevonden voor deze zoekcombinatie."}"""

                response = claude.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=800,
                    system=systeem_prompt,
                    messages=gesprek
                )

                antwoord = response.content[0].text
                st.markdown(antwoord)

                if bronnen:
                    with st.expander(f"📄 Gebruikte bronnen ({len(bronnen)})"):
                        detectie = []
                        if auto_producttype: detectie.append(f"producttype → **{auto_producttype}**")
                        if auto_ondergrond:  detectie.append(f"ondergrond → **{auto_ondergrond}**")
                        if detectie:
                            st.caption(f"🔍 Gedetecteerd: {', '.join(detectie)}")
                            st.divider()
                        for bron, score in bronnen:
                            st.caption(f"• {bron}  _(score: {score})_")

        st.session_state.berichten.append({"rol": "assistant", "tekst": antwoord})
        # Reset antwoorden voor volgende vraag
        st.session_state.antwoorden    = {}
        st.session_state.originele_vraag = None
