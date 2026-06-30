import streamlit as st
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from rapidfuzz import process, fuzz
import graphviz
import os
import json
import re
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI      = "bolt+ssc://p-mt-2a41353b6b9a-1-0090.production-orch-0695.neo4j.io:7687"
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "f9c5be28"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ── Fresh connection every time to avoid defunct connection errors ─────────────
def run_query(cypher, params=None):
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        max_connection_lifetime=60,
        keep_alive=True
    )
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(cypher, **(params or {}))
            return [dict(r) for r in result]
    except Exception as e:
        st.error(f"Database error: {e}")
        return []
    finally:
        driver.close()

@st.cache_resource
def get_llm():
    return ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0)

@st.cache_data(ttl=300)
def get_all_entities():
    rows = run_query("MATCH (n) RETURN n.name AS name, labels(n)[0] AS type")
    return [(r["name"], r["type"]) for r in rows if r["name"]]

# ── Step 1: Deep Query Understanding via LLM ──────────────────────────────────
def understand_query(question, all_entity_names):
    sample = ", ".join(all_entity_names[:100])
    prompt = f"""You are an agricultural query analyzer. Deeply understand what the user is asking,
even if phrased in an unusual, indirect, or conversational way.

Known entities in our database (sample): {sample}

Common agricultural knowledge:
- Stem Borer, Brown Plant Hopper, Leaf Folder, Gall Midge → Pests of Rice
- Blast, Sheath Blight, Brown Spot, Bacterial Leaf Blight → Diseases of Rice
- Aphids, Jassids, Sawfly, Painted Bug → Pests of Wheat/Mustard
- Rust, Smut, Powdery Mildew, Loose Smut → Diseases of Wheat
- Bollworm, Whitefly, Thrips, Jassids → Pests of Cotton
- Wilt, Root Rot, Leaf Curl → Diseases of Cotton
- Carbofuran, Chlorpyriphos, Monocrotophos → Pesticides for Rice pests
- Tricyclazole, Isoprothiolane, Carbendazim → Fungicides for Rice Blast
- Imidacloprid, Dimethoate, Oxydemeton → Pesticides for Aphids

Intent mapping rules:
- "what if i don't use pesticide" → consequence_query (user wants to know what happens)
- "what happens if stem borer is not controlled" → consequence_query
- "which crop is grown in Punjab" → location_query (reverse lookup)
- "what crops need nitrogen" → nutrient_query (reverse lookup)
- "which pesticide kills aphids" → pesticide_query
- "how to protect rice from blast" → prevention_query
- "what should I spray on wheat" → pesticide_query
- "rice blast treatment" → pesticide_query
- "side effects of not treating stem borer" → consequence_query
- "best time to grow wheat" → season_query
- "wheat growing regions" → location_query
- "which crops are kharif crops" → season_query
- "fertilizer schedule for rice" → nutrient_query
- "organic control of aphids" → pesticide_query
- "natural enemies of stem borer" → prevention_query
- "symptoms of rice blast" → symptom_query
- "signs of wheat rust" → symptom_query

Intent options:
pest_query, disease_query, pesticide_query, location_query,
season_query, nutrient_query, symptom_query, prevention_query,
consequence_query, general_query

Return ONLY valid JSON (no markdown, no explanation):
{{
  "intent": "...",
  "reasoning": "brief explanation",
  "crops": ["crop names mentioned or inferred"],
  "pests": ["pest names mentioned or inferred"],
  "diseases": ["disease names mentioned or inferred"],
  "locations": ["location/state names if any"],
  "reverse_lookup": false
}}

Question: {question}

JSON:"""
    llm = get_llm()
    response = llm.invoke(prompt).content
    try:
        clean = re.sub(r"```json|```", "", response).strip()
        return json.loads(clean)
    except:
        return {
            "intent": "general_query",
            "reasoning": "Could not parse intent",
            "crops": [], "pests": [], "diseases": [],
            "locations": [], "reverse_lookup": False
        }

# ── Step 2: Fuzzy Entity Resolution ──────────────────────────────────────────
def fuzzy_match_name(name, entity_names, threshold=78):
    match = process.extractOne(name, entity_names, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        return match[0]
    return None

def resolve_entities(parsed, all_entities):
    entity_names    = [e[0] for e in all_entities]
    entity_type_map = {e[0]: e[1] for e in all_entities}
    resolved = {}
    for crop in parsed.get("crops", []):
        m = fuzzy_match_name(crop, entity_names)
        if m: resolved[m] = entity_type_map.get(m, "Crop")
    for pest in parsed.get("pests", []):
        m = fuzzy_match_name(pest, entity_names)
        if m: resolved[m] = entity_type_map.get(m, "Pest")
    for disease in parsed.get("diseases", []):
        m = fuzzy_match_name(disease, entity_names)
        if m: resolved[m] = entity_type_map.get(m, "Disease")
    for loc in parsed.get("locations", []):
        m = fuzzy_match_name(loc, entity_names)
        if m: resolved[m] = entity_type_map.get(m, "Location")
    return resolved

# ── Step 3: Targeted Neo4j Queries ───────────────────────────────────────────
def query_graph(intent, resolved_entities, parsed, question):
    results = []

    crops    = [n for n, t in resolved_entities.items() if t == "Crop"]
    pests    = [n for n, t in resolved_entities.items() if t == "Pest"]
    diseases = [n for n, t in resolved_entities.items() if t == "Disease"]
    locations= [n for n, t in resolved_entities.items() if t in ("State","Location","Country","District")]

    # ── PEST QUERY ────────────────────────────────────────────────────────────
    if intent in ("pest_query", "consequence_query"):
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(p:Pest)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'AFFECTED_BY' AS relation,
                       p.name AS target, 'Pest' AS target_type LIMIT 15
            """, {"name": crop})
            results.extend(rows)
        for pest in pests:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(p:Pest)
                WHERE toLower(p.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'AFFECTED_BY' AS relation,
                       p.name AS target, 'Pest' AS target_type LIMIT 15
            """, {"name": pest})
            results.extend(rows)

    # ── DISEASE QUERY ─────────────────────────────────────────────────────────
    if intent in ("disease_query", "consequence_query"):
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(d:Disease)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'AFFECTED_BY' AS relation,
                       d.name AS target, 'Disease' AS target_type LIMIT 15
            """, {"name": crop})
            results.extend(rows)
        for disease in diseases:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(d:Disease)
                WHERE toLower(d.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'AFFECTED_BY' AS relation,
                       d.name AS target, 'Disease' AS target_type LIMIT 15
            """, {"name": disease})
            results.extend(rows)

    # ── PESTICIDE QUERY ───────────────────────────────────────────────────────
    if intent == "pesticide_query":
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:CONTROLLED_BY]->(p)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'CONTROLLED_BY' AS relation,
                       p.name AS target, labels(p)[0] AS target_type LIMIT 15
            """, {"name": crop})
            results.extend(rows)
        for pest in pests:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(p:Pest)
                WHERE toLower(p.name) CONTAINS toLower($name)
                WITH c
                MATCH (c)-[:CONTROLLED_BY]->(x)
                RETURN c.name AS source, 'CONTROLLED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 15
            """, {"name": pest})
            results.extend(rows)
        for disease in diseases:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(d:Disease)
                WHERE toLower(d.name) CONTAINS toLower($name)
                WITH c
                MATCH (c)-[:CONTROLLED_BY]->(x)
                RETURN c.name AS source, 'CONTROLLED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 15
            """, {"name": disease})
            results.extend(rows)

    # ── LOCATION QUERY ────────────────────────────────────────────────────────
    if intent == "location_query":
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:GROWN_IN]->(s)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'GROWN_IN' AS relation,
                       s.name AS target, labels(s)[0] AS target_type LIMIT 20
            """, {"name": crop})
            results.extend(rows)
        for loc in locations:
            rows = run_query("""
                MATCH (c:Crop)-[:GROWN_IN]->(s)
                WHERE toLower(s.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'GROWN_IN' AS relation,
                       s.name AS target, labels(s)[0] AS target_type LIMIT 20
            """, {"name": loc})
            results.extend(rows)

    # ── SEASON QUERY ──────────────────────────────────────────────────────────
    if intent == "season_query":
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:GROWN_DURING]->(s:Season)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'GROWN_DURING' AS relation,
                       s.name AS target, 'Season' AS target_type LIMIT 10
            """, {"name": crop})
            results.extend(rows)

    # ── NUTRIENT QUERY ────────────────────────────────────────────────────────
    if intent == "nutrient_query":
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:REQUIRES]->(n)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'REQUIRES' AS relation,
                       n.name AS target, labels(n)[0] AS target_type LIMIT 15
            """, {"name": crop})
            results.extend(rows)

    # ── SYMPTOM QUERY ─────────────────────────────────────────────────────────
    if intent == "symptom_query":
        for disease in diseases:
            rows = run_query("""
                MATCH (d:Disease)-[:HAS_SYMPTOM]->(s)
                WHERE toLower(d.name) CONTAINS toLower($name)
                RETURN d.name AS source, 'HAS_SYMPTOM' AS relation,
                       s.name AS target, labels(s)[0] AS target_type LIMIT 10
            """, {"name": disease})
            results.extend(rows)
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(d:Disease)-[:HAS_SYMPTOM]->(s)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN d.name AS source, 'HAS_SYMPTOM' AS relation,
                       s.name AS target, 'Symptom' AS target_type LIMIT 10
            """, {"name": crop})
            results.extend(rows)

    # ── PREVENTION QUERY ──────────────────────────────────────────────────────
    if intent == "prevention_query":
        for crop in crops:
            rows = run_query("""
                MATCH (c:Crop)-[:PREVENTED_BY]->(x)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'PREVENTED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 10
            """, {"name": crop})
            results.extend(rows)
            rows2 = run_query("""
                MATCH (c:Crop)-[:CONTROLLED_BY]->(x)
                WHERE toLower(c.name) CONTAINS toLower($name)
                RETURN c.name AS source, 'CONTROLLED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 10
            """, {"name": crop})
            results.extend(rows2)
        for disease in diseases:
            rows = run_query("""
                MATCH (d:Disease)-[:PREVENTED_BY]->(x)
                WHERE toLower(d.name) CONTAINS toLower($name)
                RETURN d.name AS source, 'PREVENTED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 10
            """, {"name": disease})
            results.extend(rows)
        for pest in pests:
            rows = run_query("""
                MATCH (c:Crop)-[:AFFECTED_BY]->(p:Pest)
                WHERE toLower(p.name) CONTAINS toLower($name)
                WITH c
                MATCH (c)-[:CONTROLLED_BY]->(x)
                RETURN c.name AS source, 'CONTROLLED_BY' AS relation,
                       x.name AS target, labels(x)[0] AS target_type LIMIT 10
            """, {"name": pest})
            results.extend(rows)

    # ── GENERAL FALLBACK ──────────────────────────────────────────────────────
    if not results:
        all_names = list(resolved_entities.keys())
        if all_names:
            rows = run_query("""
                MATCH (n)-[rel]->(m)
                WHERE n.name IN $names OR m.name IN $names
                RETURN n.name AS source, type(rel) AS relation,
                       m.name AS target, labels(m)[0] AS target_type LIMIT 25
            """, {"names": all_names})
            results.extend(rows)

    return results

# ── Step 4: Answer Generation with GPT Fallback ───────────────────────────────
def generate_answer(question, graph_context, intent, reasoning):
    llm = get_llm()

    if graph_context:
        context_str = "\n".join([
            f"{r['source']} --[{r['relation']}]--> {r['target']}"
            for r in graph_context
        ])
        prompt = f"""You are an agricultural expert assistant.

Based ONLY on the following knowledge graph triples, answer the user's question.
Format the answer clearly and list all relevant items found.
Do NOT add information not in the data below.

Knowledge Graph Triples:
{context_str}

User Question: {question}
Detected Intent: {intent}

Answer:"""
        answer = llm.invoke(prompt).content
        return answer, "graph"

    else:
        prompt = f"""You are an agricultural expert assistant with deep knowledge of Indian agriculture.

The knowledge graph did not have specific data for this question.
Answer based on your agricultural expertise. Be specific and practical.

Important: Start your answer with "⚠️ Note: This answer is from general AI knowledge, not from the verified database."

Question: {question}

Answer:"""
        answer = llm.invoke(prompt).content
        return answer, "fallback"

# ── Step 5: Focused Subgraph ──────────────────────────────────────────────────
def build_focused_subgraph(used_triples):
    dot = graphviz.Digraph(
        graph_attr={"bgcolor": "#1e1e2e", "rankdir": "LR"},
        node_attr={"style": "filled", "fontcolor": "white", "fontsize": "11"},
        edge_attr={"color": "#aaaaaa", "fontcolor": "#dddddd", "fontsize": "9"}
    )
    color_map = {
        "Crop": "#2ecc71", "Disease": "#e74c3c", "Pest": "#e67e22",
        "Pesticide": "#9b59b6", "Fertilizer": "#3498db", "Soil": "#795548",
        "Season": "#00bcd4", "Location": "#f39c12", "State": "#f39c12",
        "District": "#ff9800", "Country": "#ffeb3b", "Weather": "#607d8b",
        "Irrigation": "#1abc9c", "Nutrient": "#27ae60", "FarmerPractice": "#8e44ad",
        "Symptom": "#ff6b6b",
    }
    src_type_map = {
        "AFFECTED_BY": "Crop", "CONTROLLED_BY": "Crop",
        "GROWN_IN": "Crop", "GROWN_DURING": "Crop",
        "REQUIRES": "Crop", "HAS_SYMPTOM": "Disease",
        "PREVENTED_BY": "Crop", "CAUSES": "Pest",
    }
    added_nodes = set()
    for row in used_triples:
        src   = row.get("source", "")
        tgt   = row.get("target", "")
        rel   = row.get("relation", "")
        ttype = row.get("target_type", "")
        stype = src_type_map.get(rel, "")
        if src and src not in added_nodes:
            dot.node(src, src, fillcolor=color_map.get(stype, "#607d8b"), shape="ellipse")
            added_nodes.add(src)
        if tgt and tgt not in added_nodes:
            dot.node(tgt, tgt, fillcolor=color_map.get(ttype, "#607d8b"), shape="ellipse")
            added_nodes.add(tgt)
        if src and tgt:
            dot.edge(src, tgt, label=rel)
    return dot

# ── UI ─────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AgriGraphRAG", page_icon="🌾", layout="wide")
st.title("🌾 AgriGraphRAG — Explainable Agricultural QA")
st.markdown(
    "Ask any agricultural question in **natural language**. "
    "Answers are grounded in a Neo4j Knowledge Graph with GPT-4o-mini fallback."
)

with st.sidebar:
    st.header("📌 Entity Legend")
    st.markdown("🟢 **Crop** | 🔴 **Disease** | 🟠 **Pest**")
    st.markdown("🟣 **Pesticide** | 🔵 **Fertilizer** | 🟤 **Soil**")
    st.markdown("🟡 **Location/State** | ⚪ **Weather** | 🩵 **Irrigation**")
    st.markdown("🔴 **Symptom** | 🟤 **FarmerPractice**")
    st.markdown("---")
    st.markdown("**Pipeline:**")
    st.markdown("1. 🧠 LLM understands intent")
    st.markdown("2. 🔍 RapidFuzz matches entities")
    st.markdown("3. 🗄️ Neo4j targeted query")
    st.markdown("4. ✅ Graph-grounded answer")
    st.markdown("5. 🔄 GPT fallback if no data")
    st.markdown("6. 🕸️ Focused subgraph shown")

st.markdown("### 💡 Sample Questions")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🌾 Pests in Rice?"):
        st.session_state["query"] = "What pests affect Rice?"
with col2:
    if st.button("🍚 Control Stem Borer?"):
        st.session_state["query"] = "How to control Stem Borer?"
with col3:
    if st.button("🌱 Fertilizers for Paddy?"):
        st.session_state["query"] = "What fertilizers does Paddy need?"
col4, col5, col6 = st.columns(3)
with col4:
    if st.button("🐛 Diseases in Cotton?"):
        st.session_state["query"] = "What diseases affect Cotton?"
with col5:
    if st.button("🌍 Crops in Punjab?"):
        st.session_state["query"] = "Which crops are grown in Punjab?"
with col6:
    if st.button("💊 Prevent Rice Blast?"):
        st.session_state["query"] = "How to prevent Rice Blast?"

query = st.text_input(
    "🔍 Enter your agricultural question:",
    value=st.session_state.get("query", ""),
    placeholder="e.g. What if I don't use pesticide for stem borer?"
)

if st.button("🚀 Get Answer", type="primary") and query:

    with st.spinner("🧠 Understanding your question..."):
        all_entities     = get_all_entities()
        all_entity_names = [e[0] for e in all_entities]
        parsed           = understand_query(query, all_entity_names)
        intent           = parsed.get("intent", "general_query")
        reasoning        = parsed.get("reasoning", "")
        resolved         = resolve_entities(parsed, all_entities)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        intent_emoji = {
            "pest_query": "🐛", "disease_query": "🦠",
            "pesticide_query": "💊", "location_query": "🌍",
            "season_query": "🌤️", "nutrient_query": "🌱",
            "symptom_query": "🔬", "prevention_query": "🛡️",
            "consequence_query": "⚠️", "general_query": "❓"
        }
        emoji = intent_emoji.get(intent, "❓")
        st.markdown(f"**{emoji} Intent Detected:** `{intent}`")
        st.caption(f"💭 *{reasoning}*")
    with col_b:
        if resolved:
            st.markdown("**📌 Matched Entities:**")
            for name, etype in resolved.items():
                st.markdown(f"- `{name}` → **{etype}**")
        else:
            st.info("No specific entities matched — will use GPT-4o-mini fallback.")

    with st.spinner("🗄️ Searching Knowledge Graph..."):
        graph_context = query_graph(intent, resolved, parsed, query)

    with st.spinner("✍️ Generating answer..."):
        answer, source = generate_answer(query, graph_context, intent, reasoning)

    st.markdown("### 📋 Answer")
    if source == "graph":
        st.success(answer)
        st.caption("✅ **Source: Knowledge Graph** — Answer grounded in verified Neo4j database.")
    else:
        st.info(answer)
        st.warning(
            "⚠️ **Fallback Mode:** The knowledge graph did not contain data for this question. "
            "Answer generated by GPT-4o-mini from general knowledge. Please verify from official sources."
        )

    if graph_context:
        with st.expander(f"📊 Knowledge Graph Triples Used ({len(graph_context)} records)"):
            st.dataframe(pd.DataFrame(graph_context))

    st.markdown("### 🕸️ Reasoning Subgraph")
    st.caption("Shows ONLY the triples used to generate the answer above.")

    if graph_context:
        dot = build_focused_subgraph(graph_context)
        st.graphviz_chart(dot.source)
    else:
        st.warning("No subgraph — answer was from GPT-4o-mini general knowledge.")

st.markdown("---")
st.markdown(
    "<center>Explainable GraphRAG for Precision Agriculture | "
    "Devdeep Banerjee | DR. B.C. ROY ENGINEERING COLLEGE</center>",
    unsafe_allow_html=True
)