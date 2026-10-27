# LLM-IFC varianten

Drie proefopstellingen om een IFC-bouwmodel in natuurlijke taal te bevragen met een (lokaal) taalmodel. Elke variant gebruikt een andere manier om het model aan de LLM te koppelen. Zo kun je de aanpakken met elkaar vergelijken.

| Map | Aanpak | Kern |
|---|---|---|
| [260525_variant_01](260525_variant_01/) | **Vaste MCP-tools** | De LLM kiest uit vooraf gedefinieerde tools zonder parameters, die elk één specifieke vraag beantwoorden. |
| [260525_variant_02](260525_variant_02/) | **Parametrische MCP-tools** | Twee stappen: eerst de beschikbare waarden in het model ontdekken, daarna generieke tools met die exacte waarden aanroepen. |
| [260524_variant_03](260524_variant_03/) | **GraphRAG met Neo4j** | Het IFC-model wordt in een Neo4j-graaf geladen. De LLM schrijft Cypher-queries om vragen te beantwoorden. |

Elke variant staat op zichzelf, met een eigen `requirements.txt`, `.env.example` en `README.md` met installatie- en gebruiksinstructies.

## Gemeenschappelijke benodigdheden

- Python 3.11 of hoger
- [Ollama](https://ollama.com/download) met een lokaal taalmodel (variant 03 kan ook OpenAI gebruiken)
- Een eigen IFC-bestand (`.ifc`). Deze zitten **niet** in de repository.
- Alleen voor variant 03: Docker Desktop (voor Neo4j)

## Snel starten

```powershell
cd 260525_variant_01          # of een andere variant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # pas daarna de waarden aan
```

Zie daarna de README van de betreffende variant.

## Logging

Alle varianten schrijven per sessie een gestructureerd logbestand naar `logs\`, met per vraag de prompt, de tool-aanroepen of queries, de resultaten en het antwoord van de LLM. Daarmee kun je de varianten met elkaar vergelijken. Logbestanden worden niet meegecommit.

## Licentie

[MIT](LICENSE)
