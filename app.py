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

st.title("SmartTDS Verfassistent")
st.write("Stel een vraag over verfproducten en krijg een antwoord op basis van de technische datasheets.")

if "berichten" not in st.session_state:
    st.session_state.berichten = []

for bericht in st.session_state.berichten:
    with st.chat_message(bericht["rol"]):
        st.write(bericht["tekst"])

vraag = st.chat_input("Stel je vraag...")

if vraag:
    st.session_state.berichten.append({"rol": "user", "tekst": vraag})
    with st.chat_message("user"):
        st.write(vraag)

    with st.chat_message("assistant"):
        with st.spinner("Zoeken in datasheets..."):
            embedding = model.encode(vraag).tolist()
            resultaten = supabase.rpc("zoek_documenten", {
                "query_embedding": embedding,
                "aantal": 5
            }).execute()

            context = "\n\n".join([
                f"Product: {r['product_naam']}\n{r['inhoud']}"
                for r in resultaten.data
            ])

            prompt = "Je bent een technisch assistent voor verfproducten.\n"
            prompt += "Beantwoord de vraag op basis van de onderstaande productinformatie.\n"
            prompt += "Antwoord in het Nederlands.\n\n"
            prompt += "Productinformatie:\n" + context + "\n\n"
            prompt += "Vraag: " + vraag

            antwoord = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            tekst = antwoord.content[0].text
            st.write(tekst)
            st.session_state.berichten.append({"rol": "assistant", "tekst": tekst})