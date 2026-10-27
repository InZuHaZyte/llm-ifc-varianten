"""
Streamlit-UI voor de IFC GraphRAG-pipeline.

Starten:
    streamlit run streamlit_app.py

Vereist een draaiende Neo4j (docker compose up -d) en een geldige LLM-configuratie
in .env (OPENAI_API_KEY voor OpenAI, of OLLAMA_BASE_URL/OLLAMA_MODEL voor Ollama).
"""
from pathlib import Path

import streamlit as st

from agents.graph_agent import GraphAgent
from config import get_config
from graph.neo4j_client import Neo4jClient
from ifc.graph_builder import GraphBuilder
from ifc.parser import IFCParser
from logging_config import setup_logging
from session_log import SessionLogger

st.set_page_config(page_title="IFC GraphRAG", page_icon="🏗️", layout="wide")

cfg = get_config()
setup_logging(cfg.log)


@st.cache_resource
def get_client() -> Neo4jClient:
    return Neo4jClient(cfg.neo4j.uri, cfg.neo4j.user, cfg.neo4j.password)


@st.cache_resource
def get_agent(_client: Neo4jClient) -> GraphAgent:
    return GraphAgent(cfg, _client)


def get_session_logger() -> SessionLogger:
    if "session_logger" not in st.session_state:
        st.session_state.session_logger = SessionLogger()
    return st.session_state.session_logger


client = get_client()

# ---------------------------------------------------------------------------
# Sidebar — status en IFC-model laden
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Status")

    using_openai = bool(cfg.openai.api_key.strip())
    if using_openai:
        st.write(f"**LLM:** OpenAI — `{cfg.openai.model}`")
        if not cfg.openai.api_key.startswith("sk-") or cfg.openai.api_key == "sk-proj":
            st.warning("OPENAI_API_KEY in .env lijkt geen geldige sleutel — vul je echte key in.")
    else:
        st.write(f"**LLM:** Ollama — `{cfg.ollama.model}` @ {cfg.ollama.base_url}")

    try:
        schema = client.get_schema_summary()
        st.success("Neo4j verbonden")
        with st.expander("Graph-schema (Neo4j)"):
            st.text(schema)
    except Exception as exc:
        st.error(f"Neo4j niet bereikbaar: {exc}")

    st.divider()
    st.subheader("IFC-model laden")
    default_ifc = Path("IFC_modellen/Schependomlaan/IFC Schependomlaan.ifc")
    ifc_path = st.text_input("Pad naar .ifc-bestand", value=str(default_ifc))
    clear_first = st.checkbox("Graph eerst legen", value=True)

    if st.button("Model inladen in Neo4j", use_container_width=True):
        with st.spinner("IFC-model wordt geparsed en ingeladen — dit kan een minuut duren..."):
            try:
                if clear_first:
                    client.clear_graph()
                client.setup_schema()
                model = IFCParser(ifc_path).parse()
                data = GraphBuilder().build(model)
                client.load_graph_data(data)
                st.success(f"Geladen: {data.summary()}")
            except Exception as exc:
                st.error(f"Laden mislukt: {exc}")

    st.divider()
    if st.button("Chat wissen", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Hoofdscherm — chat
# ---------------------------------------------------------------------------
st.title("🏗️ IFC GraphRAG")
st.caption("Stel een vraag in gewone taal over het gebouwmodel dat in Neo4j is geladen.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Bijv. 'Wat is de totale vloeroppervlakte per verdieping?'")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Bezig met analyseren van het model..."):
            try:
                agent = get_agent(client)
                result = agent.run(question)
                st.markdown(result.answer)

                with st.expander("Details — Cypher & resultaten"):
                    if result.discovery_cypher:
                        st.caption("Discovery-Cypher (stap 1)")
                        st.code(result.discovery_cypher, language="cypher")
                    st.caption("Hoofd-Cypher (stap 2)")
                    st.code(result.cypher, language="cypher")
                    if result.raw_results:
                        st.caption(f"Resultaten ({len(result.raw_results)} records)")
                        st.dataframe(result.raw_results, use_container_width=True)
                    else:
                        st.caption("Geen resultaten gevonden.")
                    st.caption(
                        f"Latency: totaal={result.latency_total_ms:.0f}ms | "
                        f"cypher-generatie={result.latency_cypher_ms:.0f}ms | "
                        f"query={result.latency_query_ms:.0f}ms | "
                        f"antwoord={result.latency_answer_ms:.0f}ms"
                    )

                get_session_logger().log(result)
                st.session_state.messages.append({"role": "assistant", "content": result.answer})
            except Exception as exc:
                st.error(f"Er ging iets mis: {exc}")
