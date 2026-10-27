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
  (:Site      {name, guid, description, elevation})
  (:Building  {name, guid, description})
  (:Storey    {name, guid, elevation, long_name})
  (:Space     {name, guid, long_name, occupancy, area, height, volume, acoustic_rating})
  (:Wall      {name, guid, type_name, load_bearing, is_external, fire_rating, acoustic_rating,
               reference, area, length, height, width, volume, material, material_layers})
  (:Door      {name, guid, type_name, overall_height, overall_width, fire_rating, acoustic_rating,
               area, material})
  (:Window    {name, guid, type_name, overall_height, overall_width, fire_rating, acoustic_rating,
               area, material})
  (:Slab      {name, guid, type_name, load_bearing, is_external, fire_rating, acoustic_rating,
               area, length, width, volume, material, material_layers})
  (:Roof      {name, guid, type_name, is_external, fire_rating,
               area, volume, material, material_layers})
  (:Stair     {name, guid, type_name, fire_rating, acoustic_rating,
               length, height, width, volume})
  (:Covering  {name, guid, type_name, fire_rating, acoustic_rating,
               area, length, width, volume, material, material_layers})
  (:Column    {name, guid, type_name, load_bearing, is_external, fire_rating,
               area, length, volume, material, material_layers})
  (:Beam      {name, guid, type_name, load_bearing, fire_rating,
               area, length, volume, material, material_layers})
  (:Railing   {name, guid, type_name, fire_rating,
               area, length, height, volume, material, material_layers})
  (:Member    {name, guid, type_name, load_bearing, fire_rating,
               area, length, volume, material, material_layers})

Relaties:
  (:Project)  -[:CONTAINS]->     (:Site)
  (:Site)     -[:CONTAINS]->     (:Building)
  (:Building) -[:CONTAINS]->     (:Storey)
  (:Storey)   -[:CONTAINS]->     (:Space | :Wall | :Door | :Window | :Slab | :Roof | :Stair | :Covering | :Column | :Beam | :Railing | :Member)
  (:Wall)     -[:ON_STOREY]->    (:Storey)
  (:Space)    -[:ON_STOREY]->    (:Storey)
  (:Door)     -[:ON_STOREY]->    (:Storey)
  (:Window)   -[:ON_STOREY]->    (:Storey)
  (:Slab)     -[:ON_STOREY]->    (:Storey)
  (:Roof)     -[:ON_STOREY]->    (:Storey)
  (:Stair)    -[:ON_STOREY]->    (:Storey)
  (:Covering) -[:ON_STOREY]->    (:Storey)
  (:Column)   -[:ON_STOREY]->    (:Storey)
  (:Beam)     -[:ON_STOREY]->    (:Storey)
  (:Railing)  -[:ON_STOREY]->    (:Storey)
  (:Member)   -[:ON_STOREY]->    (:Storey)
  (:Wall)     -[:BOUNDS_SPACE]-> (:Space)
  (:Slab)     -[:BOUNDS_SPACE]-> (:Space)
  (:Column)   -[:BOUNDS_SPACE]-> (:Space)
  (:Covering) -[:BOUNDS_SPACE]-> (:Space)
  (:Door)     -[:FILLS_OPENING]->(:Wall)
  (:Window)   -[:FILLS_OPENING]->(:Wall)

Eenheden (tenzij anders vermeld):
  - area, volume  → m²  /  m³  (IFC-eenheden, doorgaans SI)
  - length, height, width → meters  (width = dikte voor wand/vloer/afwerking; dwarsdoorsnede voor kolom/balk)
  - material_layers → JSON-string met [{name, thickness_mm}] per laag
  - elevation → meter boven nulpeil

Belangrijke properties:
  - load_bearing  (boolean)  — dragende elementen
  - is_external   (boolean)  — buitengevel/dak
  - fire_rating   (string)   — bijv. "EI 60"
  - acoustic_rating (string) — bijv. "Rw 52 dB"
  - type_name     (string)   — objecttype/familienaam
  - reference     (string)   — wandtype-referentie
  - material      (string)   — primair materiaal
  - material_layers (string) — JSON met alle materiaallagen en dikte in mm

BELANGRIJK — (:Space) is een RUIMTE (kamer), GEEN appartement/wooneenheid:
  Eén appartement bestaat uit meerdere (:Space)-nodes (slaapkamer, badkamer, keuken, ...).
  Er is GEEN apart (:Apartment)-nodetype — wooneenheden zijn alleen af te leiden uit de
  naamgeving: sp.name volgt het patroon '<eenheid>.<kamernummer>', bijv. '3.04' = kamer 04
  van eenheid 3. Namen die met een letter beginnen (bijv. 'A0.01') zijn ALGEMENE/gedeelde
  ruimtes (trappenhuis, entree, berging) en horen bij GEEN enkel appartement.
  Vraag NOOIT count(sp) om "hoeveel appartementen" te beantwoorden — dat telt ruimtes, niet
  wooneenheden. Splits sp.name op '.' en tel de DISTINCT eenheid-prefixes (zie voorbeeld).

BELANGRIJK — fundering heeft GEEN eigen nodetype (geen IfcFooting/IfcPile in dit model):
  Funderingselementen zijn gewoon (:Beam)-nodes met een herkenbare naam, bijv. 'fund_strook',
  'fund_opstort', 'fund_poer'. Ze liggen op de verdieping (:Storey {name: '-1 fundering'}).
  Concludeer dus NOOIT "de fundering is onbekend" enkel omdat er geen Slab/Wall met
  type_name='Fundering' bestaat — zoek eerst op naam (toLower(e.name) CONTAINS 'fund') of via
  de storey '-1 fundering' voordat je concludeert dat iets niet in de graaf zit.
"""

# ------------------------------------------------------------------
# Stap 1: Discovery prompt
# ------------------------------------------------------------------

DISCOVERY_PROMPT = """\
Je bent een assistent die IFC-gebouwmodellen in Neo4j bevraagt.

TAAK: Bepaal of de onderstaande vraag filtert op een NAAM, VERDIEPING, TYPE of MATERIAAL
die je niet van tevoren kent en die je eerst uit de database moet ophalen.

Verdiepingsnamen, ruimtenamen en elementtypen zijn modelspecifiek.
Voorbeelden: "begane grond" kan in de database "00 begane grond" zijn.
             "verdieping 3" kan "03 derde verdieping" of "03" zijn.
             "beton" kan als materiaal "Beton C20/25" zijn.

WANNEER discovery NIET nodig is (antwoord dan exact "NONE"):
- Tellen zonder filter:       "hoeveel ramen zijn er?"
- Filter op boolean property: "alle dragende wanden", "buitenwanden", "dragende vloeren"
- Filter op bestaand getal:   "wanden met fire_rating > 60"
- Opsomming zonder filter:    "geef alle ruimtes", "welke verdiepingen zijn er?", "welke kolommen zijn er?"

WANNEER discovery WEL nodig is:
- Filter op een naam die je niet kent: "ramen op de begane grond",
  "ruimtes op verdieping 2", "vloeren van type XYZ", "kolommen van beton"

Kies de minst uitgebreide discovery-query die voldoende is:
  - Verdiepingsnamen:  MATCH (s:Storey)   RETURN s.name, s.elevation ORDER BY s.elevation
  - Ruimtenamen:       MATCH (s:Space)    RETURN s.name, s.long_name  ORDER BY s.name
  - Wandtypen:         MATCH (w:Wall)     RETURN DISTINCT w.reference, w.type_name ORDER BY w.reference
  - Deurtypen:         MATCH (d:Door)     RETURN DISTINCT d.type_name  ORDER BY d.type_name
  - Vloertypen:        MATCH (sl:Slab)    RETURN DISTINCT sl.type_name ORDER BY sl.type_name
  - Kolomtypen:        MATCH (c:Column)   RETURN DISTINCT c.type_name, c.material ORDER BY c.type_name
  - Balktypen:         MATCH (b:Beam)     RETURN DISTINCT b.type_name, b.material ORDER BY b.type_name
  - Materialen (wand): MATCH (w:Wall)     RETURN DISTINCT w.material   ORDER BY w.material
  - Materialen (vloer):MATCH (sl:Slab)    RETURN DISTINCT sl.material  ORDER BY sl.material
  - Elementen op naam gezocht (bijv. fundering, iets dat geen eigen nodetype heeft):
                       MATCH (e) WHERE toLower(e.name) CONTAINS '<zoekterm>'
                       RETURN DISTINCT labels(e), e.name ORDER BY e.name

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
[discovery gaf: name: 00 begane grond | name: 01 eerste verdieping]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(sp:Space)
WHERE sp.name = '3.03'
WITH st
MATCH (st)-[:CONTAINS]->(w:Window)
RETURN DISTINCT w.name AS raam, st.name AS verdieping

Vraag: "Hoeveel deuren zijn er per verdieping?"
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(d:Door)
RETURN st.name AS verdieping, count(d) AS aantal_deuren
ORDER BY st.elevation

Vraag: "Hoeveel ramen en deuren zijn er per verdieping?"
Cypher:
MATCH (st:Storey)
OPTIONAL MATCH (st)-[:CONTAINS]->(win:Window)
OPTIONAL MATCH (st)-[:CONTAINS]->(d:Door)
WITH st, count(DISTINCT win) AS aantal_ramen, count(DISTINCT d) AS aantal_deuren
WHERE aantal_ramen > 0 OR aantal_deuren > 0
RETURN st.name AS verdieping, aantal_ramen, aantal_deuren
ORDER BY st.elevation

Vraag: "Welke buitenwanden zijn brandwerend?"
Cypher:
MATCH (w:Wall)
WHERE w.is_external = true AND w.fire_rating <> ''
RETURN w.name AS wand, w.fire_rating AS brandweerstand, w.reference AS type

Vraag: "Wat is de totale vloeroppervlakte per verdieping?"
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(sl:Slab)
WHERE sl.area IS NOT NULL
RETURN st.name AS verdieping, round(sum(sl.area), 2) AS totaal_oppervlak_m2
ORDER BY st.elevation

Vraag: "Welke vloeren zijn draagconstructie?"
Cypher:
MATCH (sl:Slab)
WHERE sl.load_bearing = true
RETURN sl.name AS vloer, sl.type_name AS type, sl.material AS materiaal

Vraag: "Wat zijn de materiaallagen van de buitenwanden?"
Cypher:
MATCH (w:Wall)
WHERE w.is_external = true AND w.material_layers <> ''
RETURN w.name AS wand, w.material AS primair_materiaal, w.material_layers AS lagen

Vraag: "Welke kolommen staan op de begane grond?"
[discovery gaf: name: 00 begane grond | elevation: 0.0]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(c:Column)
WHERE st.name = '00 begane grond'
RETURN c.name AS kolom, c.type_name AS type, c.material AS materiaal

Vraag: "Wat is het totale volume van alle betonnen wanden?"
[discovery gaf: material: Beton C20/25]
Cypher:
MATCH (w:Wall)
WHERE w.material = 'Beton C20/25' AND w.volume IS NOT NULL
RETURN count(w) AS aantal, round(sum(w.volume), 3) AS totaal_volume_m3

Vraag: "Welke ruimtes hebben een akoestische classificatie?"
Cypher:
MATCH (sp:Space)
WHERE sp.acoustic_rating IS NOT NULL AND sp.acoustic_rating <> ''
RETURN sp.name AS ruimte, sp.long_name AS type, sp.acoustic_rating AS akoestiek
ORDER BY sp.name

Vraag: "Wat zijn de afwerklagen (coverings) op de eerste verdieping?"
[discovery gaf: name: 01 eerste verdieping | elevation: 3.2]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(cov:Covering)
WHERE st.name = '01 eerste verdieping'
RETURN cov.name AS afwerking, cov.type_name AS type, cov.material AS materiaal

Vraag: "Welke ruimtes worden begrensd door dragende wanden op verdieping 1?"
[discovery gaf: name: 01 eerste verdieping | elevation: 3.2]
Cypher:
MATCH (st:Storey)-[:CONTAINS]->(w:Wall)-[:BOUNDS_SPACE]->(sp:Space)
WHERE w.load_bearing = true AND st.name = '01 eerste verdieping'
RETURN DISTINCT sp.name AS ruimte, st.name AS verdieping, collect(w.name) AS wanden

Vraag: "Wat is er bekend over de fundering?"
[discovery gaf: labels: ['Beam'] | name: fund_opstort  //  labels: ['Beam'] | name: fund_poer  //  labels: ['Beam'] | name: fund_strook]
Cypher:
MATCH (e)
WHERE toLower(e.name) CONTAINS 'fund'
RETURN labels(e) AS elementtype, e.name AS naam, e.material AS materiaal, e.volume AS volume_m3
ORDER BY e.name

Vraag: "Hoeveel appartementen heeft dit complex?"
Cypher:
MATCH (sp:Space)
WHERE sp.name =~ '[0-9]+\\..*'
WITH DISTINCT split(sp.name, '.')[0] AS eenheid
RETURN count(eenheid) AS aantal_appartementen

Vraag: "Welke ruimtes horen bij appartement 3?"
Cypher:
MATCH (sp:Space)
WHERE sp.name STARTS WITH '3.'
RETURN sp.name AS ruimte, sp.long_name AS type, sp.area AS oppervlak_m2
ORDER BY sp.name

Vraag: "Geef een overzicht van alle elementen met brandclassificatie EI 60."
Cypher:
MATCH (e)
WHERE e.fire_rating = 'EI 60'
RETURN labels(e) AS elementtype, e.name AS naam, e.type_name AS type
ORDER BY elementtype, naam
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
- RETURN uitsluitend de velden die nodig zijn om de vraag te beantwoorden (meestal naam,
  eventueel type ter identificatie). Voeg GEEN extra velden toe zoals area, volume, length,
  material of fire_rating als de vraag daar niet expliciet naar vraagt — ook niet als een
  vergelijkbaar voorbeeld hierboven die wel toont.
- Als er BESCHIKBARE WAARDEN zijn: gebruik EXACT die waarden. Niet gokken of parafraseren.
- Voor "op dezelfde verdieping als X": gebruik het CONTAINS-patroon via Storey:
    MATCH (st:Storey)-[:CONTAINS]->(ref:<Type>) WHERE ref.name = 'X'
    WITH st
    MATCH (st)-[:CONTAINS]->(doel:<Type>)
- Voor "op welke verdieping zit X": gebruik (st:Storey)-[:CONTAINS]->(x) WHERE x.name = 'X'
- Voor totalen/sommen: gebruik sum() met round(..., 2) voor leesbaarheid.
- Gebruik DISTINCT om duplicaten te voorkomen.
- Case-insensitieve vergelijkingen: gebruik toLower() alleen als er GEEN exacte waarde beschikbaar is.
- material_layers is een JSON-string; retourneer hem as-is of filter op w.material voor materiaalvragen.

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
Vermeld relevante getallen, namen en eenheden uit de resultaten.
Bij oppervlaktes en volumes: vermeld altijd de eenheid (m² of m³).

ANTWOORD:"""
