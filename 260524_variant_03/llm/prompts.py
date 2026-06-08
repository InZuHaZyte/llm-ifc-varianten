"""
Prompt-templates voor de twee-staps pipeline:
  1. DISCOVERY_PROMPT         — beslist welke waarden te ontdekken
  2. CYPHER_GENERATION_TEMPLATE — genereert de hoofd-Cypher (met exacte waarden)
  3. ANSWER_GENERATION_TEMPLATE — formuleert het eindantwoord

De LLM krijgt NOOIT het volledige IFC-model, alleen het graph-schema
en de actuele waarden die via discovery zijn opgehaald.
"""

# ------------------------------------------------------------------
# Graph schema — statische context
# ------------------------------------------------------------------

GRAPH_SCHEMA = """
GRAPH SCHEMA (Neo4j):

Node-types:
  (:Project   {name, guid, description})
  (:Building  {name, guid, description})
  (:Storey    {name, guid, elevation, long_name})
  (:Space     {name, guid, long_name, occupancy})
  (:Wall      {name, guid, load_bearing, is_external, fire_rating, reference})
  (:Door      {name, guid, type_name, overall_height, overall_width, fire_rating})
  (:Window    {name, guid, type_name, overall_height, overall_width})

Relaties:
  (:Project)  -[:CONTAINS]->     (:Building)
  (:Building) -[:CONTAINS]->     (:Storey)
  (:Storey)   -[:CONTAINS]->     (:Space | :Wall | :Door | :Window)
  (:Wall)     -[:ON_STOREY]->    (:Storey)
  (:Space)    -[:ON_STOREY]->    (:Storey)
  (:Door)     -[:ON_STOREY]->    (:Storey)
  (:Window)   -[:ON_STOREY]->    (:Storey)
  (:Wall)     -[:BOUNDS_SPACE]-> (:Space)
  (:Door)     -[:FILLS_OPENING]->(:Wall)
  (:Window)   -[:FILLS_OPENING]->(:Wall)

Belangrijke properties:
  - load_bearing  (boolean)  — dragende wanden
  - is_external   (boolean)  — buitengevel
  - fire_rating   (string)   — bijv. "EI 60"
  - reference     (string)   — wandtype-referentie
  - elevation     (float)    — vloerhoogte in meters
  - long_name     (string)   — volledige naam van ruimte/verdieping
"""

# ------------------------------------------------------------------
# Stap 1: Discovery prompt
# ------------------------------------------------------------------

DISCOVERY_PROMPT = """\
Je bent een assistent die IFC-gebouwmodellen in Neo4j bevraagt.

TAAK: Bepaal of de onderstaande vraag filtert op een NAAM, VERDIEPING of TYPE
die je niet van tevoren kent en die je eerst uit de database moet ophalen.

Verdiepingsnamen, ruimtenamen en wandtypes zijn modelspecifiek.
Voorbeelden: "begane grond" kan in de database "00 begane grond" zijn.
             "verdieping 3" kan "03 derde verdieping" of "03" zijn.
             "ruimte 3.04" moet exact overeenkomen met de database-waarde.

WANNEER discovery NIET nodig is (antwoord dan exact "NONE"):
- Tellen zonder filter:       "hoeveel ramen zijn er?"
- Filter op boolean property: "alle dragende wanden", "buitenwanden"
- Filter op bestaand getal:   "wanden met fire_rating > 60"
- Opsomming zonder filter:    "geef alle ruimtes", "welke verdiepingen zijn er?"

WANNEER discovery WEL nodig is:
- Filter op een naam die je niet kent: "ramen op de begane grond",
  "ruimtes op verdieping 2", "wanden van type XYZ", "ruimte 3.04"

Kies de minst uitgebreide discovery-query die voldoende is:
  - Verdiepingsnamen:  MATCH (s:Storey) RETURN s.name, s.elevation ORDER BY s.elevation
  - Ruimtenamen:       MATCH (s:Space)  RETURN s.name, s.long_name  ORDER BY s.name
  - Wandtypen:         MATCH (w:Wall)   RETURN DISTINCT w.reference  ORDER BY w.reference
  - Deurtypen:         MATCH (d:Door)   RETURN DISTINCT d.type_name  ORDER BY d.type_name

Antwoord ALLEEN met "NONE" of met de discovery Cypher-query. Geen uitleg.

VRAAG: {question}

ANTWOORD:"""

# ------------------------------------------------------------------
# Voorbeeld-queries voor few-shot prompting (stap 2)
# ------------------------------------------------------------------

EXAMPLE_QUERIES = """
VOORBEELDEN:

Vraag: "Op welke verdieping zit ruimte 3.04 en wat voor ruimte is het?"
[discovery gaf: name: 3.04 | long_name: Keuken]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(sp:Space)
WHERE sp.name = '3.04'
RETURN st.name AS verdieping, sp.long_name AS ruimte_type

Vraag: "Welke ramen bevinden zich op dezelfde verdieping als ruimte 3.03?"
[discovery gaf: name: 00 begane grond | name: 01 eerste verdieping | name: 02 tweede verdieping]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(sp:Space)
WHERE sp.name = '3.03'
WITH st
MATCH (st)-[:CONTAINS]->(w:Window)
RETURN DISTINCT w.name AS raam, st.name AS verdieping

Vraag: "Welke ruimtes liggen op dezelfde verdieping als ruimte 2.04?"
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(ref:Space)
WHERE ref.name = '2.04'
WITH st
MATCH (st)-[:CONTAINS]->(sp:Space)
WHERE sp.name <> '2.04'
RETURN sp.name AS ruimte, sp.long_name AS type, st.name AS verdieping

Vraag: "Welke ramen zijn er op de begane grond?"
[discovery gaf: name: 00 begane grond | elevation: 0.0]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(w:Window)
WHERE st.name = '00 begane grond'
RETURN w.name AS raam, w.type_name AS type

Vraag: "Welke dragende wanden grenzen aan ruimte 'Kantoor 01'?"
Cypher:
MATCH (w:Wall)-[:BOUNDS_SPACE]->(sp:Space)
WHERE sp.name = 'Kantoor 01' AND w.load_bearing = true
RETURN w.name AS wand, w.fire_rating AS brandweerstand

Vraag: "Hoeveel deuren zijn er per verdieping?"
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(d:Door)
RETURN st.name AS verdieping, count(d) AS aantal_deuren
ORDER BY st.elevation

Vraag: "Welke buitenwanden zijn brandwerend?"
Cypher:
MATCH (w:Wall)
WHERE w.is_external = true AND w.fire_rating <> ''
RETURN w.name AS wand, w.fire_rating AS brandweerstand, w.reference AS type

Vraag: "Welke ruimtes worden begrensd door dragende wanden op verdieping 1?"
[discovery gaf: name: 01 eerste verdieping | elevation: 3.2]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(w:Wall)-[:BOUNDS_SPACE]->(sp:Space)
WHERE w.load_bearing = true AND st.name = '01 eerste verdieping'
RETURN DISTINCT sp.name AS ruimte, st.name AS verdieping, collect(w.name) AS wanden
"""

# ------------------------------------------------------------------
# Stap 2: Cypher-generatie (met optionele discovery-context)
# ------------------------------------------------------------------

CYPHER_GENERATION_TEMPLATE = """\
Je bent een expert in Neo4j Cypher voor IFC-gebouwmodellen.
Genereer uitsluitend een geldige Cypher-query op basis van de onderstaande vraag.

{schema}

{examples}

{discovery_context}
REGELS:
- Gebruik alleen node-types en relaties uit het schema hierboven.
- Retourneer ALLEEN de Cypher-query, geen uitleg, geen markdown-codeblokken.
- Als er BESCHIKBARE WAARDEN zijn: gebruik EXACT die waarden. Niet gokken of parafraseren.
- Voor "op dezelfde verdieping als X": gebruik het CONTAINS-patroon via Storey:
    MATCH (st:Storey)-[:CONTAINS]->(ref:<Type>) WHERE ref.name = 'X'
    WITH st
    MATCH (st)-[:CONTAINS]->(doel:<Type>)
- Voor "op welke verdieping zit X": gebruik (st:Storey)-[:CONTAINS]->(x) WHERE x.name = 'X'
- Gebruik DISTINCT om duplicaten te voorkomen.
- Case-insensitieve vergelijkingen: gebruik toLower() alleen als er GEEN exacte waarde beschikbaar is.

VRAAG: {question}

CYPHER:"""

# ------------------------------------------------------------------
# Stap 3: Antwoordgeneratie
# ------------------------------------------------------------------

ANSWER_GENERATION_TEMPLATE = """\
Je bent een behulpzame assistent voor bouwtechnische vragen.
Geef een duidelijk, leesbaar antwoord in het Nederlands op basis van de query-resultaten hieronder.

Originele vraag: {question}

Gebruikte Cypher-query:
{cypher}

Resultaten uit de database:
{results}

Formuleer een beknopt en informatief antwoord. Als er geen resultaten zijn, zeg dat dan eerlijk.
Vermeld relevante getallen en namen uit de resultaten.

ANTWOORD:"""
