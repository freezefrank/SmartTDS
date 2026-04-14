# SmartTDS — Vragenflow Productselectie

> **Status:** Concept / in onderzoek  
> **Doel:** Een logische, efficiënte vragenflow ontwikkelen die de juiste TDS-documenten ophaalt  
> **Scope:** Voorlopig alleen productselectievragen, omdat we nu primair TDS-documenten hebben  
> **Buiten scope (voor later):** probleemdiagnose, klachten, kleurvragen (vereisen kennisartikelen)

---

## Intentiedetectie — vóór de boom

Voordat de vragenflow start, detecteert de app de intentie:

| Intentie | Signalen | Actie |
|---|---|---|
| **Productinformatie** | Productnaam in vraag (Rubbol, Cetol, Redox…) | Direct zoeken — geen vragen |
| **Productselectie** | "Welke", "wat voor", "adviseer", "zoek" | Start beslisboom hieronder |
| **Probleemdiagnose** | "Bladert", "hecht niet", "trekt", "scheurt" | *Buiten scope — kennisartikelen nodig* |
| **Klacht** | "Kapot", "klacht", "schade", "garantie" | *Buiten scope* |
| **Kleurvraag** | "Kleur", "tint", "RAL", "NCS" | *Buiten scope* |

---

## Stap 1 — Ondergrond *(altijd eerste vraag)*

De ondergrond is de meest bepalende factor voor productselectie.  
Vraag: **"Wat is de ondergrond?"**

```
Metaal      → Tak A
Hout        → Tak B
Beton/steen → Tak C
Muur/gips   → Tak D
Kunststof   → Tak E
```

---

## Tak A — Metaal

```
A1. Ferro of non-ferro?
    ├── Ferro (staal, ijzer, gegalvaniseerd)
    └── Non-ferro (aluminium, zink, koper, messing)

A2. Kaal of geschilderd?
    ├── Kaal/onbehandeld
    │     └── → A3
    └── Voorzien van verflaag
          ├── Welk type verflaag?
          │     ├── Watergedragen (muurverf/emulsie)
          │     ├── Alkyd/olieverf
          │     ├── Epoxy of PU-coating
          │     └── Weet ik niet
          ├── Conditie verflaag?
          │     ├── Goed gehecht, gave oppervlak
          │     ├── Lichte afschilfering/krijtvorming
          │     └── Slechte conditie/veel afschilfering
          └── → A3

A3. Binnen of buiten?

A4. Bijzondere eisen? (optioneel)
    ├── Hittebestendig (uitlaatpijpen, radiatoren)
    ├── Chemisch bestendig
    ├── Zware corrosie (C4/C5 — industrie, marine, kust)
    └── Geen bijzondere eisen
```

**Zoekvelden:** ondergrond=metaal, ferro/non-ferro → ondergrond filter, toepassing=binnen/buiten

---

## Tak B — Hout

```
B1. Kaal of geschilderd?
    ├── Kaal/onbehandeld
    │     └── → B2
    └── Voorzien van verflaag
          ├── Welk type verflaag?
          │     ├── Dekkende verf/lak
          │     ├── Beits of vernis (transparant)
          │     ├── Grondverf/primer
          │     └── Weet ik niet
          ├── Conditie verflaag?
          │     ├── Goed gehecht
          │     ├── Lichte afschilfering
          │     └── Slechte conditie
          └── → B2

B2. Binnen of buiten?
    ├── Buiten
    │     └── B2a. Houtsoort?
    │               ├── Zachthout (vuren, grenen, douglas)
    │               ├── Hardhout (meranti, teak, iroko, accoya)
    │               └── Weet ik niet / anders
    └── Binnen → B3

B3. Gewenst eindresultaat?
    ├── Dekkend (verf of lak — houtnerf niet zichtbaar)
    └── Transparant (beits of vernis — houtnerf zichtbaar)
```

**Zoekvelden:** ondergrond=hout, toepassing=binnen/buiten, producttype=beits/lak/primer

**Onderzoekspunt:** Hardhout heeft andere primers nodig (extractieven blokkeren hechting).  
Vraag: hebben we voor Accoya/Teak aparte TDS-en of staat dit in generieke hout-TDS?

---

## Tak C — Beton / Steen / Metselwerk

```
C1. Binnen of buiten?

C2. Nieuw of oud?
    ├── Nieuw (< 1 jaar) — carbonatatie nog niet volledig
    └── Oud / bestaand

C3. Bijzondere omstandigheden? (optioneel)
    ├── Vochtproblemen / optrekkend vocht
    ├── Uitbloei / efflorescence (witte kalkuitslag)
    ├── Schimmel of algen
    └── Geen bijzonderheden
```

**Zoekvelden:** ondergrond=beton of steen, toepassing=binnen/buiten

---

## Tak D — Muur / Gips / Gipsplaat

```
D1. Nieuw of al eerder geschilderd?
    ├── Nieuw (voorstrijk/fixeer nodig)
    └── Geschilderd

D2. Bijzondere eisen? (optioneel)
    ├── Vochtige ruimte (badkamer, keuken)
    ├── Dampdoorlatend vereist
    ├── Schimmelwerend
    └── Geen bijzonderheden
```

**Zoekvelden:** ondergrond=gips of muur, toepassing=binnen (bijna altijd)  
**Noot:** Locatie hoeft niet gevraagd te worden — muurverf is vrijwel altijd binnen.

---

## Tak E — Kunststof

```
E1. Type kunststof?
    ├── PVC (kozijnen, dakgoten)
    ├── Polyester of glasvezel
    ├── Polyurethaan
    └── Weet ik niet / anders

E2. Binnen of buiten?
```

**Onderzoekspunt:** Hebben we voldoende kunststof-TDS in de database? Controleren per merk.

---

## Stap 2 — Producttype *(na ondergrond)*

Soms al duidelijk uit de vraag, anders vragen:

| Signaal in vraag | Detectie |
|---|---|
| "primer", "grondverf", "grondlaag", "voorstrijk" | → primer |
| "eindlaag", "aflak", "topcoat", "deklaag" | → eindlaag |
| "beits" | → beits |
| "lak", "vernis" | → lak |
| "vulmiddel", "plamuur" | → vulmiddel |
| Niets gevonden | → vraag: "Zoek je een grondverf, eindlaag, of een compleet verfsysteem?" |

---

## Stap 3 — Markt + Segment *(na ondergrond + producttype)*

Pas daarna, want dan is het resultaat al sterk gefilterd en is de merklijst zinvoller.

| Sidebar | Actie |
|---|---|
| Markt = NL of BE | Overslaan |
| Markt = Beide | Vragen: 🇳🇱 NL / 🇧🇪 BE / Beide |
| Segment = PROF of DIY | Overslaan |
| Segment = Beide | Vragen: Professioneel / Particulier / Beide |

---

## Stap 4 — Merk *(optioneel)*

Alleen vragen als er nog geen merkvoorkeur is én de merklijst zinvol gefilterd is op markt+segment.

---

## Volgorde samengevat

```
Huidige volgorde (app):    Markt → Segment → Ondergrond → Locatie → Merk
Gewenste volgorde (boom):  Ondergrond → [Subvragen per materiaal] → Producttype → Markt → Segment → Merk
```

---

## Openstaande onderzoekspunten

1. **Hardhout** — Hebben we TDS-en die specifiek hardhout/extractieven-problematiek behandelen?
2. **Kunststof** — Hoeveel kunststof-TDS-en zitten er in de database? Takje E zinvol?
3. **Corrosieklassen** — Staat C3/C4/C5 (ISO 12944) in de metaal-TDS-en? Zo ja → vraag toevoegen
4. **Houtsoorten buiten** — Moeten we Accoya apart behandelen? (speciale primers vereist)
5. **Overheen schilderen** — Dit raakt productselectie én systeem; hoe integreer je dit in de boom?
6. **Compleet verfsysteem** — Klant vraagt soms om de hele opbouw (grond + tussenlak + eindlaag). Aparte flow?

---

## Implementatienotes

- De vragenflow moet per tak andere `pending_vraag`-stappen doorlopen
- Takdetectie op basis van `detecteer_ondergrond()` → geeft de tak
- Elk tak-antwoord vult `antwoorden` + wordt meegenomen in `verrijkte_vraag`
- Vragen die al duidelijk zijn uit de originele vraag altijd overslaan
- Vrij tekstveld blijft altijd beschikbaar naast de keuzeknopjes

---

*Laatste update: april 2026*
