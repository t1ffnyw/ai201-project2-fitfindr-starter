# FitFindr

FitFindr is an AI agent that searches a mock secondhand listings database, suggests outfits based on a user's wardrobe, and generates a shareable fit card caption. The agent runs a conditional planning loop — each tool is only called when the previous step succeeds.

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the CLI test:

```bash
python agent.py
```

Run the Gradio UI:

```bash
python app.py
```

Run the tool tests:

```bash
python -m pytest tests/test_tools.py -v
```

## Project Structure

```
ai201-project2-fitfindr-starter/
├── agent.py              # Planning loop and session state
├── app.py                # Gradio UI
├── tools.py              # Three agent tools
├── planning.md           # Design spec and architecture diagram
├── data/
│   ├── listings.json     # 40 mock secondhand listings
│   └── wardrobe_schema.json
├── utils/
│   └── data_loader.py    # load_listings(), get_example_wardrobe(), etc.
└── tests/
    └── test_tools.py     # Pytest tests for each tool
```

---

## Tool Inventory

### 1. `search_listings`

| | |
|---|---|
| **Purpose** | Search the mock listings dataset for items matching a keyword description, optional size, and optional price ceiling. |
| **Inputs** | `description` (`str`)  keywords describing what the user wants (e.g. `"vintage graphic tee"`) |
| | `size` (`str \| None`) size filter; case-insensitive substring match (e.g. `"M"` matches `"S/M"`) |
| | `max_price` (`float \| None`) maximum price inclusive |
| **Output** | `list[dict]`  matching listing dicts sorted by relevance (best match first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` on no match. |

### 2. `suggest_outfit`

| | |
|---|---|
| **Purpose** | Given a thrifted listing and the user's wardrobe, suggest 1–2 complete outfits (top, bottom, shoes minimum) using Groq's `llama-3.3-70b-versatile`. |
| **Inputs** | `new_item` (`dict`)  a listing dict from `search_listings` |
| | `wardrobe` (`dict`)  wardrobe with an `items` key containing a list of wardrobe item dicts |
| **Output** | `str`  outfit suggestion text from the LLM. If the wardrobe is empty, returns general styling advice instead of crashing. |

### 3. `create_fit_card`

| | |
|---|---|
| **Purpose** | Generate a short, shareable 2–4 sentence Instagram/TikTok caption for the outfit using Groq's `llama-3.3-70b-versatile` at temperature 0.9 for output variety. |
| **Inputs** | `outfit` (`str`)  the outfit suggestion string from `suggest_outfit` |
| | `new_item` (`dict`)  the listing dict for the thrifted item |
| **Output** | `str`  a casual OOTD caption mentioning the item name, price, and platform. Returns an error message string if `outfit` is empty or whitespace-only. |

---

## Planning Loop

The agent's entry point is `run_agent(query, wardrobe)` in `agent.py`. It follows a strict sequential loop with early exits on failure:

1. **Initialize session**: create a fresh session dict via `_new_session()`.
2. **Parse query**: extract `description`, `size`, and `max_price` from the natural language query using regex (`_parse_query()`).
3. **Search**: call `search_listings(description, size, max_price)`. Store results in `session["search_results"]`.
4. **Branch on results**: if the list is empty, set `session["error"] = "No matching items found."` and return immediately. No further tools are called.
5. **Select item**: take the top result (`results[0]`) and store it in `session["selected_item"]`.
6. **Suggest outfit**: call `suggest_outfit(selected_item, wardrobe)`. Store the string in `session["outfit_suggestion"]`.
7. **Create fit card**: call `create_fit_card(outfit_suggestion, selected_item)`. Store the string in `session["fit_card"]`.
8. **Return session**

The agent never calls all three tools unconditionally. Each step depends on the previous step's output.

---

## State Management

All state for a single interaction lives in one session dict returned by `run_agent()`. Fields are populated progressively as tools run:

| Field | Set by | Passed to |
|---|---|---|
| `query` | `_new_session()` | na |
| `parsed` | `_parse_query()` | `search_listings()` |
| `search_results` | `search_listings()` | used to pick `selected_item` |
| `selected_item` | top result from search | `suggest_outfit()`, `create_fit_card()` |
| `wardrobe` | `_new_session()` | `suggest_outfit()` |
| `outfit_suggestion` | `suggest_outfit()` | `create_fit_card()` |
| `fit_card` | `create_fit_card()` | returned to user via `app.py` |
| `error` | set on early exit | checked first by `app.py` |

The same `selected_item` dict object flows from search into both `suggest_outfit` and `create_fit_card`. The same `outfit_suggestion` string flows from `suggest_outfit` into `create_fit_card`. No values are re-prompted or hardcoded between steps.

The Gradio handler in `app.py` reads the completed session and maps it to three output panels: formatted listing text, outfit suggestion, and fit card.

---

## Error Handling

| Tool | Failure mode | What happens | Concrete test example |
|---|---|---|---|
| `search_listings` | No listings match | Returns `[]`. Agent sets `session["error"] = "No matching items found."` and stops. | Query `"designer ballgown size XXS under $5"` → `session["error"]` is set, `session["fit_card"]` is `None`, `session["outfit_suggestion"]` is `None`. Verified via `python agent.py`. |
| `suggest_outfit` | Empty wardrobe | Tool does not crash. LLM returns general styling advice for the new item instead of referencing wardrobe pieces. | `test_suggest_outfit_empty_wardrobe` in `tests/test_tools.py` passes with mocked LLM — returns a non-empty string, no exception. |
| `create_fit_card` | Empty or whitespace outfit | Returns `"Error: No outfit provided to create a fit card."` — no exception raised. | `test_fit_card_empty_outfit` and `test_fit_card_whitespace_outfit` in `tests/test_tools.py` both pass. |

At the agent level, only the search no-results path triggers an early exit. The `suggest_outfit` and `create_fit_card` tools handle their own edge cases internally and return strings rather than crashing the loop.

---

## Spec Reflection

This section compares the final implementation against `planning.md`.

**What matches the spec:**
- Three tools with the correct names and conditional planning loop
- Early return when `search_listings` returns no results — no further tools called
- State flows through the session dict: `selected_item` → `suggest_outfit` → `outfit_suggestion` → `create_fit_card`
- Error message for no search results: `"No matching items found."`
- `create_fit_card` guards against empty outfit input

**What differs from the spec:**

| Spec (`planning.md`) | Implementation | Reason |
|---|---|---|
| `search_listings` returns max 3 items | Returns all matching items sorted by relevance | The `tools.py` docstring specifies sorted results without a cap; tests expect all price-filtered matches |
| `suggest_outfit` returns a list of clothing item dicts | Returns an `str` from the LLM | The starter `tools.py` stub signature returns `str`; the LLM naturally produces descriptive text |
| Empty wardrobe → agent returns `"Empty wardrobe"` and stops | `suggest_outfit` handles empty wardrobe internally with general styling advice; agent continues to `create_fit_card` | The `tools.py` TODO explicitly says to offer general styling advice rather than crash or return empty |
| `create_fit_card` input is a `list` | Input is `str` (the outfit suggestion text) | Matches the actual `tools.py` stub signature: `create_fit_card(outfit: str, new_item: dict)` |

---

## AI Usage

I used Claude for two major implementation milestones, following the AI Tool Plan in `planning.md`.

### Instance 1: Tool implementations 

**Input given to AI:**
- Tool 1, Tool 2, and Tool 3 sections from `planning.md` (inputs, return values, failure modes)
- The Planning Loop and Error Handling sections
- The Mermaid architecture diagram from `planning.md`
- The TODO comments and function signatures already in `tools.py`
- Explicit instructions: use `load_listings()` from `utils/data_loader.py`, use Groq `llama-3.3-70b-versatile`, write pytest tests with at least one test per failure mode

**What AI produced:**
- `search_listings()` with keyword-overlap scoring, size/price filtering
- `suggest_outfit()` and `create_fit_card()` with Groq LLM calls, empty-input guards, and temperature settings
- `tests/test_tools.py` with 11 tests including mocked Groq client for LLM tools

**What I changed or overrode:**
- Verified that `test_search_price_filter` used `"jacket"` with `max_price=10`
- Kept the implementation returning all scored results rather than capping at 3, since the starter docstring did not specify a cap

### Instance 2: Planning loop and app handler

**Input given to AI:**
- Planning Loop and State Management sections from `planning.md`
- Error Handling table from `planning.md`
- The full Mermaid architecture diagram
- The numbered TODO steps in `agent.py` and `app.py`

**What AI produced:**
- `_parse_query()` helper using regex to extract `size`, `max_price`, and `description`
- `run_agent()` with conditional tool chaining and early return on empty search
- `handle_query()` mapping session dict fields to three Gradio output strings

**What I changed or overrode:**
- Reviewed the generated `run_agent()` before running
- Chose regex parsing over LLM parsing for query extraction
- Ran `python agent.py` to verify both the happy path (`"looking for a vintage graphic tee under $30"`) and the no-results path (`"designer ballgown size XXS under $5"`) before accepting the implementation



