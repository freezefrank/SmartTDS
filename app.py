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

def is_overheen_vraag(tekst: str) -> bool:
    """Detecteer renovatie/overheen-schilderen vragen."""
    t = tekst.lower()
    return any(w in t for w in [
        "overheen", "over heen", "oververf", "over de bestaande",
        "op de oude", "op bestaande", "renovatie", "overlagen",
        "overcoat", "op het huidige", "op mijn huidige", "hier overheen"
    ])

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

# Bekende productnaam-patronen (woorden die duiden op een exact product)
PRODUCTNAAM_SIGNALEN = [
    "rubbol", "redox", "autoclear", "alphaxylan", "cetol", "rubbol bl",
    "rezisto", "uniprimer", "multiprimer", "safira", "endurance", "isoprimer",
    "permacryl", "sigma", "levis", "hydroprimer", "flexa strak", "flexa muur"
]

def is_productnaam_zoekopdracht(vraag: str) -> bool:
    """
    Geeft True als de vraag waarschijnlijk een exacte productnaam bevat
    en dus geen verduidelijkingsvragen nodig zijn.
    """
    v = vraag.lower().strip()
    woorden = v.split()

    # Directe productnaam-signalen
    if any(p in v for p in PRODUCTNAAM_SIGNALEN):
        return True

    # Korte zoekopdracht (≤5 woorden) zonder categoriewoorden = waarschijnlijk productnaam
    categoriewoorden = {"zoek", "welke", "welk", "wat", "voor", "primer", "grondverf",
                        "eindlaag", "verf", "beits", "lak", "buiten", "binnen", "op"}
    if len(woorden) <= 5 and not any(w in categoriewoorden for w in woorden):
        return True

    return False

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
    """
    Geeft de eerstvolgende benodigde vervolgvraag terug, of None als genoeg context.
    Volgorde (conform VRAGENFLOW.md):
      0. bestaande_laag (overheen-vragen)
      1. ondergrond (ALTIJD als eerste — meest bepalend)
      2. metaaltype (ferro/non-ferro, alleen bij metaal)
      3. ondergrond_staat (kaal of geschilderd, hout/metaal)
      4. bestaande_verflaag_type (als geschilderd)
      5. verflaag_conditie (als geschilderd)
      6. locatie (binnen/buiten)
      7. markt
      8. segment
      9. merk
    """
    alles = vraag + " " + " ".join(antwoorden.values())
    producttype = detecteer_producttype(alles)
    ondergrond  = detecteer_ondergrond(alles)
    locatie     = detecteer_locatie(alles)
    metaaltype  = detecteer_metaaltype(alles)
    markt       = detecteer_markt(alles)
    segment     = detecteer_segment(alles)
    merk        = detecteer_merk(alles)

    # 0. Overheen schilderen: wat is de bestaande laag?
    if is_overheen_vraag(vraag) and "bestaande_laag" not in antwoorden:
        return {
            "key": "bestaande_laag",
            "vraag": "Wat is de bestaande laag waarover geschilderd wordt?",
            "opties": [
                "Bestaande muurverf (watergedragen)",
                "Bestaande alkyd/olieverf",
                "Bestaande lak of vernis",
                "Bestaande grondverf/primer",
                "Onbehandeld hout",
                "Onbehandeld metaal",
                "Beton of steen",
                "Weet ik niet"
            ]
        }

    # 1. Ondergrond — ALTIJD als eerste vraag (tenzij al bekend uit vraag of antwoorden)
    if not ondergrond and "ondergrond" not in antwoorden:
        return {
            "key": "ondergrond",
            "vraag": "Wat is de ondergrond?",
            "opties": ["Metaal 🔩", "Hout 🪵", "Beton / steen 🧱", "Muur / gips 🏠", "Kunststof 🔵"]
        }

    # 2. Metaaltype: ferro of non-ferro?
    if ondergrond == "metaal" and not metaaltype and "metaaltype" not in antwoorden:
        return {
            "key": "metaaltype",
            "vraag": "Wat voor metaal?",
            "opties": ["Staal / ijzer (ferro) 🔩", "Aluminium / zink (non-ferro) ✨",
                       "Gegalvaniseerd staal", "Beide / weet ik niet"]
        }

    # 3. Kaal of voorzien van verflaag? (hout of metaal, niet bij overheen-vragen)
    if (not is_overheen_vraag(vraag)
            and ondergrond in ("hout", "metaal")
            and "ondergrond_staat" not in antwoorden):
        return {
            "key": "ondergrond_staat",
            "vraag": "Is de ondergrond kaal of voorzien van een verflaag?",
            "opties": ["Kaal / onbehandeld 🆕", "Voorzien van verflaag 🎨", "Weet ik niet"]
        }

    # 4. Als er een verflaag is: wat voor type?
    staat = antwoorden.get("ondergrond_staat", "")
    if staat.startswith("Voorzien") and "bestaande_verflaag_type" not in antwoorden:
        return {
            "key": "bestaande_verflaag_type",
            "vraag": "Wat voor verflaag is aanwezig?",
            "opties": [
                "Watergedragen (muurverf / emulsie) 💧",
                "Alkyd / olieverf 🛢️",
                "Epoxy of PU-coating 🔬",
                "Beits of vernis 🪵",
                "Weet ik niet"
            ]
        }

    # 5. Conditie van de bestaande verflaag?
    if staat.startswith("Voorzien") and "verflaag_conditie" not in antwoorden:
        return {
            "key": "verflaag_conditie",
            "vraag": "Wat is de conditie van de bestaande verflaag?",
            "opties": [
                "Goed gehecht, gave oppervlak ✅",
                "Lichte afschilfering / krijtvorming ⚠️",
                "Slechte conditie / veel afschilfering ❌",
                "Weet ik niet"
            ]
        }

    # 6. Locatie: binnen of buiten?
    # Muur/gips is bijna altijd binnen — niet vragen
    if ondergrond not in ("gips", "muur") and not locatie and "locatie" not in antwoorden:
        return {
            "key": "locatie",
            "vraag": "Binnen of buiten?",
            "opties": ["Buiten 🌤️", "Binnen 🏠", "Beide"]
        }

    # 7. Markt / land
    if markt_filter == "Beide" and not markt and "markt" not in antwoorden:
        return {
            "key": "markt",
            "vraag": "Voor welke markt / welk land?",
            "opties": ["🇳🇱 Nederland (NL)", "🇧🇪 België (BE)", "Beide landen"]
        }

    # 8. Segment
    if segment_filter == "Beide" and not segment and "segment" not in antwoorden:
        return {
            "key": "segment",
            "vraag": "Voor professioneel gebruik of particulier?",
            "opties": ["🔧 Professioneel / schilder (PROF)", "🏠 Particulier / DIY", "Beide"]
        }

    # 9. Merkvoorkeur — gefilterd op actieve markt/segment
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
    "pending_vraag": None,      # {"key", "vraag", "opties"}
    "antwoorden": {},           # {"ondergrond": "Staal/ijzer", "locatie": "Buiten", ...}
    "originele_vraag": None,    # De originele gebruikersvraag
    "persistent_context": {},   # Blijft bewaard tussen vragen: markt, segment, merk
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
        for k in ["berichten", "pending_vraag", "antwoorden", "originele_vraag", "persistent_context"]:
            st.session_state[k] = [] if k == "berichten" else {} if k in ("antwoorden", "persistent_context") else None
        st.rerun()

    # Export knop
    if st.session_state.berichten:
        regels = []
        for b in st.session_state.berichten:
            prefix = "👤 GEBRUIKER" if b["rol"] == "user" else "🤖 ASSISTENT"
            regels.append(f"{prefix}:\n{b['tekst']}\n")
        if st.session_state.get("persistent_context"):
            regels.append(f"\n[Persistente context: {st.session_state.persistent_context}]")
        export_tekst = "\n---\n".join(regels)
        st.download_button(
            label="📋 Exporteer gesprek",
            data=export_tekst,
            file_name="smarttds_gesprek.txt",
            mime="text/plain",
            use_container_width=True
        )

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

        # Keuzeknopjes
        for rij_start in range(0, len(opties), 4):
            rij  = opties[rij_start:rij_start + 4]
            cols = st.columns(len(rij))
            for i, optie in enumerate(rij):
                nummer = rij_start + i + 1
                if cols[i].button(f"{nummer}. {optie}", key=f"keuze_{rij_start}_{i}",
                                   use_container_width=True):
                    st.session_state.berichten.append({
                        "rol": "assistant",
                        "tekst": f"**{pv['vraag']}**"
                    })
                    st.session_state.berichten.append({"rol": "user", "tekst": optie})
                    st.session_state.antwoorden[pv["key"]] = optie
                    st.session_state.pending_vraag = None
                    st.rerun()

        # Vrij tekstveld als alternatief
        st.caption("Of typ je eigen antwoord:")
        with st.form(key=f"vrij_antwoord_{pv['key']}", clear_on_submit=True):
            vrij_col, knop_col = st.columns([5, 1])
            vrij_tekst = vrij_col.text_input(
                label="Vrij antwoord",
                placeholder=f"bijv. Douglas hout, Rubbol BL Primer, gegalvaniseerd staal...",
                label_visibility="collapsed"
            )
            bevestig = knop_col.form_submit_button("✓", use_container_width=True)
            if bevestig and vrij_tekst.strip():
                st.session_state.berichten.append({
                    "rol": "assistant",
                    "tekst": f"**{pv['vraag']}**"
                })
                st.session_state.berichten.append({"rol": "user", "tekst": vrij_tekst.strip()})
                st.session_state.antwoorden[pv["key"]] = vrij_tekst.strip()
                st.session_state.pending_vraag = None
                st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
vraag_input = st.chat_input("Stel je vraag...",
                             disabled=st.session_state.pending_vraag is not None)

# ── Verwerk nieuwe vraag of doorgaan na keuze ─────────────────────────────────
verwerk_nu = False
if vraag_input:
    # Nieuwe vraag: reset context maar laad persistente info (markt/segment/merk)
    st.session_state.originele_vraag = vraag_input
    st.session_state.antwoorden      = dict(st.session_state.persistent_context)
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

    # Bij exacte productnaam: sla vervolgvragen over
    if is_productnaam_zoekopdracht(originele):
        volgende = None
    else:
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

                # Fallback 3: alleen full-text + merk, geen andere filters
                # (vangt exacte productnamen op die verkeerde metadata hebben)
                if not docs and query_tekst:
                    try:
                        rpc4 = {
                            "query_embedding": embedding,
                            "query_tekst":     query_tekst,
                            "aantal":          12,
                            "rrf_k":           60,
                            "filter_merk":     actief_merk,
                        }
                        docs = supabase.rpc("zoek_documenten", rpc4).execute().data or []
                    except Exception:
                        docs = []

                # Fallback 4: volledig open — alleen vector search, geen filters
                if not docs:
                    try:
                        rpc5 = {"query_embedding": embedding, "aantal": 12}
                        docs = supabase.rpc("zoek_documenten", rpc5).execute().data or []
                    except Exception:
                        docs = []

                # Post-filter: verwijder eindlagen als er om een primer gevraagd wordt
                # (alleen bij categorie-zoekopdracht, niet bij exacte productnaam)
                if not is_productnaam_zoekopdracht(originele or verrijkte_vraag):
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
                if "bestaande_laag" in antwoorden:
                    filter_info += f" Bestaande laag: {antwoorden['bestaande_laag']}."
                if "ondergrond_staat" in antwoorden:
                    filter_info += f" Ondergrond staat: {antwoorden['ondergrond_staat']}."
                if "bestaande_verflaag_type" in antwoorden:
                    filter_info += f" Bestaande verflaag: {antwoorden['bestaande_verflaag_type']}."
                if "verflaag_conditie" in antwoorden:
                    filter_info += f" Conditie verflaag: {antwoorden['verflaag_conditie']}."

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

                # Extra instructie bij overheen-schilderen vragen
                overheen_instructie = ""
                if is_overheen_vraag(originele or verrijkte_vraag):
                    bestaande = antwoorden.get("bestaande_laag", "onbekend")
                    overheen_instructie = f"""

RENOVATIEVRAAG — bestaande laag: {bestaande}
Zoek in de TDS-context naar:
1. Sectie 'Overlaagbaarheid' of 'Verf systeem' — welke producten mogen overheen?
2. Vereiste voorbehandeling (schuren, ontvetten, primer)?
3. Wachttijd voordat overheen geschilderd mag worden?
Geef alleen producten die expliciet geschikt zijn voor deze bestaande laag."""

                # Instructie bij geschilderde ondergrond
                verflaag_instructie = ""
                if antwoorden.get("ondergrond_staat", "").startswith("Voorzien"):
                    vtype = antwoorden.get("bestaande_verflaag_type", "onbekend")
                    cond  = antwoorden.get("verflaag_conditie", "onbekend")
                    verflaag_instructie = f"""

GESCHILDERDE ONDERGROND — type: {vtype} | conditie: {cond}
Zoek in de TDS-context naar:
1. Voorbereiding: schuren, ontvetten, verwijderen losse verf (afhankelijk van conditie)?
2. Compatibiliteit: mag deze primer op {vtype}?
3. Aanbevolen primer voor renovatie op bestaande laag.
Bij slechte conditie: adviseer verwijdering of gebruik van een hechtprimer."""

                systeem_prompt = f"""Je bent een deskundige technisch assistent voor verfproducten van AkzoNobel Benelux.
Je helpt medewerkers van de technische supportafdeling om klanten snel en correct te helpen.

STRIKTE REGELS:
- Beantwoord UITSLUITEND op basis van de meegeleverde TDS-context. Gebruik NOOIT algemene verfkennis.
- Als het antwoord NIET in de datasheets staat: zeg "Geen TDS beschikbaar voor dit product."
- Let op [type: ...]: een [type: eindlaag] is GEEN primer, ook al noemt die TDS een primer.
- Noem altijd de exacte productnaam en het merk uit de context.
- Antwoord in het Nederlands. Bondig en praktisch — medewerker heeft klant aan de lijn.
- STEL NOOIT ZELF VRAGEN aan de gebruiker. De interface regelt alle verduidelijkingsvragen via knoppen. Als er informatie ontbreekt, geef dan het best mogelijke antwoord op basis van wat je hebt en vermeld kort welke info voor een completer advies handig zou zijn — maar stel geen vragen in vraagvorm.
- VERFSYSTEMEN: noem alleen systemen (grondlaag → tussenlaag → eindlaag) die letterlijk in één en dezelfde TDS beschreven staan. Combineer NOOIT zelf producten uit verschillende TDS-documenten tot een eigen systeem — dat kan technisch onjuist zijn. Als de TDS geen volledig systeem beschrijft, zeg dan dat de klant contact moet opnemen voor systeemadvies.
- WATERGEDRAGEN vs. ALKYD: wees alert op de basis van producten. Een watergedragen primer mag niet zomaar worden afgewerkt met een alkyd-eindlaag. Vermeld de basis (watergedragen / oplosmiddelhoudend / epoxy / PU) zodat de medewerker de compatibiliteit kan beoordelen.{filter_info}{overheen_instructie}{verflaag_instructie}

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
        # Bewaar markt/segment/merk binnen het gesprek — worden alleen gereset bij "Gesprek wissen"
        PERSISTENTE_KEYS = {"markt", "segment", "merk"}
        for k, v in antwoorden.items():
            if k in PERSISTENTE_KEYS:
                st.session_state.persistent_context[k] = v
        # Reset antwoorden voor volgende vraag
        st.session_state.antwoorden    = {}
        st.session_state.originele_vraag = None
