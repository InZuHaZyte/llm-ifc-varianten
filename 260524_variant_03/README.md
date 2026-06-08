# Variant 03 — GraphRAG met Neo4j

Het IFC-model wordt eenmalig ingeladen in een Neo4j-graaf. Daarna genereert de LLM Cypher-queries om vragen te beantwoorden. De aanpak bestaat uit twee stappen:
1. **Discovery** (indien nodig) — de LLM haalt eerst exacte namen/types op uit de graaf
2. **Query** — de LLM genereert de uiteindelijke Cypher-query en formuleert het antwoord

---

## Benodigdheden

| Software | Versie | Download |
|---|---|---|
| Python | 3.11 of hoger | https://www.python.org/downloads/ |
| Docker Desktop | nieuwste | https://www.docker.com/products/docker-desktop/ |
| Ollama | nieuwste | https://ollama.com/download |
| IFC-bestand | — | eigen model (`.ifc`) |

Na installatie van Ollama: download een taalmodel.

```powershell
ollama pull mistral-small:24b
```

> Docker Desktop moet draaien voordat je Neo4j start.

---

## Installatie

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Configuratie

Maak een `.env` bestand aan in deze map (kopieer van `.env.example`):

```powershell
Copy-Item .env.example .env
```

De standaardwaarden werken direct als je alles lokaal draait:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral-small:24b
```

> Gebruik je Ollama op een andere computer? Pas dan `OLLAMA_BASE_URL` aan naar het IP-adres van die machine, bijv. `http://192.168.1.10:11434`.

---

## Opstarten

### Stap 1 — Neo4j starten

```powershell
docker compose up -d
```

Neo4j draait nu op `http://localhost:7474` (inloggen met `neo4j` / `password123`).

### Stap 2 — IFC-model inladen

Dit hoef je maar één keer te doen (of opnieuw als je een ander model wilt laden):

```powershell
python app.py load --ifc "C:\pad\naar\jouw\model.ifc" --clear
```

### Stap 3 — Vragen stellen

Start de interactieve chat:

```powershell
python app.py
```

Je ziet welk sessie-logbestand wordt aangemaakt. Typ daarna gewoon je vraag en druk op Enter. Typ `exit` om te stoppen.

**Voorbeeld:**
```
Vraag: Welke ruimtes zijn er op de begane grond?

╔══ [1/2] Discovery Cypher ═══════════════╗
  MATCH (s:Storey) RETURN s.name, s.elevation ORDER BY s.elevation

╔══ [2/2] Hoofd-Cypher ═══════════════════╗
  MATCH (st:Storey {name: "00 begane grond"})-[:CONTAINS]->(sp:Space) RETURN sp.name

╔══ Antwoord ═════════════════════════════╗
  Op de begane grond zijn 6 ruimtes: ...
```

---

## Neo4j stoppen

```powershell
docker compose down
```

---

## Logging

Na elke sessie vind je een gestructureerd logbestand in de map `logs\`:

```
logs\sessie_variant03_20240608_143022.log   ← per sessie, 4-stappen overzicht
graphrag.log                                ← technisch logboek
```

Het sessie-logbestand toont per vraag: de prompt, de gegenereerde Cypher-queries, de Neo4j-resultaten en het LLM-antwoord.
