# Variant 01 — Vaste MCP-tools

De LLM heeft 27 vaste tools beschikbaar (bijv. `count_walls`, `list_doors_per_floor`). Het model kiest de meest passende tool en geeft een antwoord. Er zijn geen vrije parameters — elke tool doet één specifieke vraag.

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
IFC Variant 01 — typ 'exit' om te stoppen.
Sessie-log: sessie_variant_01_20240608_143022.log

> Hoeveel muren zijn er in het model?
[Tools: count_walls]
Er zijn 142 muren in het model.
```

Eenmalige vraag (zonder chatmodus):

```powershell
python client.py --question "Hoeveel deuren zijn er per verdieping?"
```

---

## Logging

Na elke sessie vind je een gestructureerd logbestand in de map `logs\`:

```
logs\sessie_variant_01_20240608_143022.log   ← per sessie, 4-stappen overzicht
logs\variant_01_client.log                   ← technisch logboek
```

Het sessie-logbestand toont per vraag: de prompt, welke tool aangeroepen werd, de tool-uitvoer en het LLM-antwoord.
