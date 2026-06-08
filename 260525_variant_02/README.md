# Variant 02 — Parametrische MCP-tools

De LLM heeft 9 flexibele tools beschikbaar. De werkwijze is altijd twee stappen:
1. **Ontdekken** — haal eerst op welke verdiepingsnamen, wandtypes, etc. er in dit model bestaan (`get_available_values`)
2. **Bevragen** — gebruik de exacte gevonden waarden als parameter in de query-tools

Dit voorkomt fouten zoals zoeken op "begane grond" terwijl het model "00 BG" gebruikt.

---

## Benodigdheden

| Software | Versie | Download |
|---|---|---|
| Python | 3.11 of hoger | https://www.python.org/downloads/ |
| Ollama | nieuwste | https://ollama.com/download |
| IFC-bestand | — | eigen model (`.ifc`) |

Na installatie van Ollama: download een taalmodel.

```powershell
ollama pull llama3.1
```

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

Pas daarna deze waarden aan:

```env
IFC_MODEL_PATH=C:\pad\naar\jouw\model.ifc
OLLAMA_MODEL=llama3.1
OLLAMA_URL=http://localhost:11434
```

> Gebruik je Ollama op een andere computer? Pas dan `OLLAMA_URL` aan naar het IP-adres van die machine, bijv. `http://192.168.1.10:11434`.

---

## Opstarten

Start de interactieve chat:

```powershell
python client.py
```

Je ziet welk sessie-logbestand wordt aangemaakt. Typ daarna gewoon je vraag en druk op Enter. Typ `exit` om te stoppen.

**Voorbeeld:**
```
IFC Variant 02 — typ 'exit' om te stoppen.
Sessie-log: sessie_variant_02_20240608_143022.log

> Hoeveel ramen zijn er op de begane grond?
[Tools: get_available_values, count_elements]
Op de begane grond (00 begane grond) zijn 18 ramen.
```

Eenmalige vraag (zonder chatmodus):

```powershell
python client.py --question "Wat is de totale bruto vloeroppervlakte?"
```

---

## Logging

Na elke sessie vind je een gestructureerd logbestand in de map `logs\`:

```
logs\sessie_variant_02_20240608_143022.log   ← per sessie, 4-stappen overzicht
logs\variant_02_client.log                   ← technisch logboek
```

Het sessie-logbestand toont per vraag: de prompt, welke tools aangeroepen werden (inclusief parameters), de tool-uitvoer en het LLM-antwoord.
