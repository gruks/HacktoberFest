# PantryPal: Architecture

## 1. Design Principles

1. **Code does the math, the model does the judgment.** All nutrition, scaling and filtering logic is deterministic Python. The LLM only chooses among pre-filtered options and rewrites text.
2. **The model can never invent facts.** It picks from candidate lists supplied by code, and its output is validated against a strict schema.
3. **Works without the model.** If Ollama is unavailable, the app still recommends, scales and calculates. Only substitutions and step rewrites are disabled.
4. **Small-model friendly.** Short prompts (< 1.5k tokens), constrained JSON output, a single model loaded at a time, designed for 4 GB VRAM.
5. **Local only.** One SQLite file plus static JSON. No network at runtime.

## 2. System Overview

```
                ┌───────────────────────────────┐
                │         Streamlit UI          │
                │ Profile | Kitchen | Cook | 🛒 │
                └──────────────┬────────────────┘
                               │
                ┌──────────────▼────────────────┐
                │          Planner              │  orchestrates the pipeline
                └──┬────────┬─────────┬─────────┘
                   │        │         │
     ┌─────────────▼─┐  ┌───▼──────┐ ┌▼────────────────┐
     │ Deterministic │  │ Subst.   │ │   LLM Adapter   │
     │ core (pure)   │  │ engine   │ │ (Ollama client) │
     │ targets       │  │ candidates│ │ JSON-schema     │
     │ filters       │  │ verify   │ │ retry/fallback  │
     │ scoring       │  │ loop     │ └───────┬─────────┘
     │ scaling       │  └───┬──────┘         │
     │ nutrition     │      │                │
     └───────┬───────┘      │        ┌───────▼─────────┐
             │              │        │ Ollama          │
     ┌───────▼──────────────▼──┐     │ qwen3:4b        │
     │   Data layer            │     │ (GPU, 4-bit)    │
     │ SQLite + JSON seeds     │     └─────────────────┘
     └─────────────────────────┘
```

## 3. Repository Layout

```
pantrypal/
├── README.md
├── PRD.md
├── ARCHITECTURE.md
├── BUILD_PLAN.md
├── requirements.txt
├── app.py                     # Streamlit entry point
├── pantrypal/
│   ├── __init__.py
│   ├── config.py              # paths, model name, tolerances
│   ├── db.py                  # SQLite connection, schema, CRUD
│   ├── models.py              # Pydantic models (Profile, Recipe, Plan, ...)
│   ├── targets.py             # BMR/TDEE, protein, per-meal targets
│   ├── nutrition.py           # lookup, sum macros/micros, cooking factors
│   ├── units.py               # unit conversion (pieces <-> grams)
│   ├── filters.py             # utensil and diet-mode filters
│   ├── scoring.py             # pantry coverage and ranking
│   ├── scaling.py             # portion scaling, carnivore ratio logic
│   ├── substitutes.py         # candidate generation, verify loop
│   ├── llm.py                 # Ollama adapter, schemas, retry, fallback
│   ├── planner.py             # end-to-end pipeline
│   └── gaps.py                # diet-mode nutrient gap flags
├── data/
│   ├── nutrition.json         # ~80 ingredients, per 100 g
│   ├── recipes.json           # ~30 curated recipes
│   ├── substitutions.json     # flavor-role substitution table
│   ├── units.json             # piece weights, staples
│   └── daily_values.json      # reference daily values
├── scripts/
│   └── build_nutrition.py     # optional: pull from USDA FDC once, cache to JSON
├── tests/
│   ├── test_targets.py
│   ├── test_nutrition.py
│   ├── test_scaling.py
│   ├── test_filters.py
│   └── test_substitutes.py
└── mcp_server.py              # optional bonus
```

## 4. Data Model

### 4.1 SQLite schema

```sql
CREATE TABLE profile (
  id              INTEGER PRIMARY KEY CHECK (id = 1),   -- single user
  diet_mode       TEXT NOT NULL,                        -- 'light_oil_healthy' | 'high_protein_carnivore'
  sex             TEXT NOT NULL,                        -- 'male' | 'female'
  age             INTEGER NOT NULL,
  height_cm       REAL NOT NULL,
  weight_kg       REAL NOT NULL,
  activity        TEXT NOT NULL,                        -- 'sedentary' | 'light' | 'moderate' | 'active'
  goal            TEXT NOT NULL,                        -- 'lose' | 'maintain' | 'gain'
  meals_per_day   INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE utensils (
  name TEXT PRIMARY KEY                                 -- 'stove', 'microwave', 'air_fryer', ...
);

CREATE TABLE pantry (
  ingredient_id TEXT PRIMARY KEY,                       -- key into nutrition.json
  quantity_g    REAL NOT NULL,                          -- stored canonically in grams
  always_have   INTEGER NOT NULL DEFAULT 0,             -- staples flag
  price_per_100g REAL,                                  -- optional, user-entered
  updated_at    TEXT NOT NULL
);

CREATE TABLE cooked_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  recipe_id   TEXT NOT NULL,
  cooked_at   TEXT NOT NULL,
  scale       REAL NOT NULL,
  rating_tags TEXT                                      -- JSON array, e.g. ["too_bland"]
);
```

Recipes, nutrition and substitutions live in JSON, not SQLite. They are read-only reference data that is easy to edit and version in git.

### 4.2 `nutrition.json` (per 100 g)

```json
{
  "chicken_thigh_raw": {
    "name": "Chicken thigh, skinless, raw",
    "category": "meat",
    "animal_based": true,
    "flavor_roles": ["bulk_protein", "umami"],
    "kcal": 121, "protein": 19.7, "carbs": 0, "fat": 4.1, "fiber": 0, "sugar": 0,
    "micros": {
      "sodium_mg": 95, "potassium_mg": 230, "calcium_mg": 8, "iron_mg": 0.9,
      "magnesium_mg": 23, "zinc_mg": 2.0, "vit_a_ug": 12, "vit_c_mg": 0,
      "vit_d_ug": 0.1, "vit_b12_ug": 0.4
    }
  }
}
```

The values above are illustrative. Fill the real ones from USDA FoodData Central (or IFCT 2017 for Indian ingredients) and spot-check them.

### 4.3 `recipes.json`

```json
{
  "id": "airfryer_lemon_chicken",
  "name": "Air Fryer Lemon Chicken Thighs",
  "diet_tags": ["light_oil_healthy", "high_protein_carnivore_optional"],
  "carnivore_ok": false,
  "requires_any": [["air_fryer"], ["oven"]],
  "servings": 2,
  "ingredients": [
    {"id": "chicken_thigh_raw", "grams": 400, "role": "bulk_protein", "essential": true},
    {"id": "lemon_juice",       "grams": 30,  "role": "acid",         "essential": false},
    {"id": "garlic",            "grams": 10,  "role": "umami",        "essential": false},
    {"id": "olive_oil",         "grams": 5,   "role": "fat",          "essential": false}
  ],
  "method": "air_fry",
  "steps": [
    "Mix the marinade ingredients and coat the chicken.",
    "Cook until the internal temperature is 74 C."
  ]
}
```

- `requires_any` is a list of alternatives. Each alternative is a set of utensils that must all be owned. A recipe passes if any alternative is satisfied.
- `essential: true` marks ingredients that can't be dropped (the main protein or base).
- `method` selects the cooking adjustment (oil absorption and retention).

### 4.4 `substitutions.json`

```json
{
  "acid": [
    {"id": "lemon_juice",   "ratio": 1.0},
    {"id": "vinegar",       "ratio": 0.5},
    {"id": "tomato",        "ratio": 3.0}
  ],
  "creaminess": [
    {"id": "greek_yogurt",  "ratio": 1.0},
    {"id": "cream",         "ratio": 0.7}
  ]
}
```

`ratio` is a starting quantity multiplier relative to the original ingredient. The verify loop adjusts it if macros drift.

## 5. Core Algorithms (deterministic)

### 5.1 Targets (`targets.py`)

```
BMR (male)   = 10*kg + 6.25*cm - 5*age + 5
BMR (female) = 10*kg + 6.25*cm - 5*age - 161
TDEE         = BMR * {sedentary 1.2, light 1.375, moderate 1.55, active 1.725}
kcal_target  = TDEE * {lose 0.85, maintain 1.00, gain 1.10}
protein_g    = weight_kg * {lose 2.0, maintain 1.8, gain 1.8}   # carnivore: +0.2, capped at 2.2
meal_target  = daily / meals_per_day
```

Cap the deficit so `kcal_target` never falls below `BMR`.

### 5.2 Filtering (`filters.py`)

A recipe is eligible when:
1. At least one alternative in `requires_any` is fully contained in the owned utensils.
2. Diet-mode rules pass:
   - **carnivore:** every ingredient, other than staples (salt, pepper, water), has `animal_based: true`.
   - **light_oil_healthy:** oil in the recipe is ≤ 10 g per serving, and the cooking method is not deep frying.

### 5.3 Coverage scoring (`scoring.py`)

```
coverage = sum(grams of recipe ingredients available in pantry, capped at required grams)
           / sum(grams of all recipe ingredients, excluding staples)
```

Rank by: `coverage` first, then fewer essential-ingredient gaps, then closeness of `recipe_kcal * scale` to the meal target.

An ingredient counts as available only if the pantry holds at least the **scaled** amount. Partial amounts count proportionally and appear in the shopping list as the shortfall.

### 5.4 Scaling (`scaling.py`)

```
scale = meal_target_kcal / (recipe_kcal / servings)
scale = clamp(scale, 0.5, 2.5)        # warn if clamped
```

**Carnivore mode:** scale only the animal ingredients. Then adjust fat-containing ingredients (butter, tallow, fattier cuts, eggs) so that `fat_g / protein_g` falls in `[0.8, 1.2]` where the pantry allows.

### 5.5 Nutrition (`nutrition.py`)

```
total = sum(grams_i / 100 * nutrient_per_100g_i)
adjusted_fat += cooking_added_oil_g(method)
micros_% = micro_total / daily_value
```

Cooking factors (`config.py`):

| Method | Added oil | Notes |
|---|---|---|
| air_fry | 3-5 g per serving | model as a light spray |
| pan_fry | 8-12 g per serving | unless the recipe declares its own fat |
| microwave | 0 g | |
| boil | 0 g | optional vitamin C retention ×0.7 |
| bake | 0-3 g | |

Retention factors are rough approximations and are labelled as such in the UI.

### 5.6 Gap flags (`gaps.py`)

Per diet mode, compare the meal's micros against `daily_values.json` pro-rated per meal. Flag any micro under 30% of its pro-rated value, and attach static advisory text (for example, "Low fiber and vitamin C are typical on a carnivore plan"). The text is static and not model-generated.

## 6. Substitution Engine

```
for each missing ingredient m in recipe:
    role       = m.role
    candidates = substitutions[role]
                 .filter(in pantry)
                 .filter(diet-compatible)
                 .filter(utensil-compatible)
                 .rank(by embedding similarity to m.id, optional, CPU)
                 [:8]
    if no candidates: mark as "to buy"; continue

    choice = LLM.pick(m, candidates, recipe_context)     # JSON, constrained
    if choice not in candidates: reject
    qty = m.grams * choice.ratio

    for attempt in 1..3:
        macros_new = recompute(recipe with swap, qty)
        drift = max(|kcal_new - kcal_old|/kcal_old, |protein_new - protein_old|/protein_old)
        if drift <= 0.10: accept; break
        qty = rebalance(qty, macros_new, macros_old)     # code, not model
    else: reject swap; mark as "to buy"
```

Why the loop is in code: 3-4B models are unreliable at arithmetic, so quantities are tuned deterministically.

## 7. LLM Layer (`llm.py`)

### 7.1 Model and runtime

- **Primary:** `qwen3:4b` through Ollama (≈ 2.5 GB at 4-bit)
- **Fallbacks (config switch):** `qwen2.5:3b-instruct`, `llama3.2:3b`
- **Embeddings (optional):** `nomic-embed-text` on CPU
- **Settings:** `temperature 0.2`, `num_ctx 2048`, thinking disabled (`think=False`, or `/no_think` in the prompt for older Ollama versions)

### 7.2 Calls

There are only two model calls, both using Ollama's structured output (`format=<JSON schema>`).

**Call A, pick a substitute**

Input (about 300 tokens): the missing ingredient and role, up to 8 candidates with their macros per 100 g, diet mode, the recipe name and the original taste profile.

```json
// Output schema
{
  "choice_id": "string (must be one of candidate ids)",
  "reason": "string (max 25 words, mention taste and macros)",
  "taste_note": "string (max 15 words)"
}
```

**Call B, rewrite steps for utensils**

Input: original steps, owned utensils, method, scaled quantities.

```json
{
  "steps": [
    {"text": "string", "minutes": "integer|null", "temp_c": "integer|null"}
  ]
}
```

### 7.3 Safety rails

| Failure | Handling |
|---|---|
| Invalid JSON or schema violation | Retry once with a shorter prompt, then fall back |
| `choice_id` not in candidates | Reject and use the top-ranked candidate by code |
| `temp_c` outside 60-260 or `minutes` outside 1-180 | Drop the rewritten step and use the original |
| Ollama unreachable | UI banner "AI features off", pipeline continues code-only |
| Slow response (> 30 s) | Timeout, then fall back |

## 8. Planner Pipeline (`planner.py`)

```
recommend(profile, utensils, pantry) -> list[Plan]

1. targets     = targets.compute(profile)
2. eligible    = filters.apply(recipes, utensils, profile.diet_mode)
3. for r in eligible:
       scale   = scaling.compute(r, targets.meal)
       cov     = scoring.coverage(r, scale, pantry)
4. top_k       = rank(eligible)[:5]
5. for r in top_k:
       r2      = substitutes.resolve(r, pantry, profile)   # may call LLM
       r2.nutrition = nutrition.sum(r2, scale, method)
       r2.gaps      = gaps.flag(r2, profile)
       r2.shopping  = shopping.list(r2, pantry)
       r2.steps     = llm.rewrite_steps(r2, utensils) or r2.steps
6. return top_k as Plan objects
```

Steps 1-4 take milliseconds. Step 5 is the only part that touches the model, so the UI shows ranked results first and fills in substitutions and rewritten steps as they finish.

## 9. UI (Streamlit)

| Screen | Contents |
|---|---|
| **Profile** | diet mode, stats, goal, meals/day; shows computed kcal and protein targets |
| **Kitchen** | utensil checkboxes; pantry table with add/edit/remove, units, staples toggle |
| **Cook** | "What can I cook?" button → ranked cards; each card expands to ingredients (have / buy / swapped), grams, macros, micros bars, gap flags, steps, "I cooked this" |
| **Shopping** | aggregated missing items, optional prices and total |

Phone access: run with `streamlit run app.py --server.address 0.0.0.0` and open the laptop's LAN IP from the phone.

## 10. Performance Budget (GTX 1650)

| Stage | Target |
|---|---|
| Filter, score, scale 30 recipes | < 50 ms |
| Model load (first call, cold) | 5-10 s |
| Substitution call | 2-6 s |
| Step rewrite call | 4-10 s |
| VRAM | ≤ 3 GB (model + 2k context) |

Keep `OLLAMA_KEEP_ALIVE` at 10 minutes or more so the model stays warm during a cooking session.

## 11. Testing Strategy

The deterministic core is fully testable without the model.

| Test | Checks |
|---|---|
| `test_targets` | known BMR/TDEE examples; kcal never below BMR |
| `test_nutrition` | hand-calculated macros for 3 recipes within 1% |
| `test_units` | egg, onion, tablespoon conversions |
| `test_filters` | recipe needing an oven is rejected without an oven; carnivore rejects plant ingredients |
| `test_scaling` | clamps, carnivore fat-to-protein ratio |
| `test_substitutes` | drift loop converges or rejects; out-of-list model choice rejected (with a mocked LLM) |

Manual check: pick 5 recipes and compare the app's macros against a calculator on the same inputs.

## 12. Security and Privacy

- Data is stored in `pantrypal.db` and local JSON, with no analytics.
- Streamlit binds to localhost by default. LAN exposure is opt-in and documented.
- Nothing in the prompts is sent off the machine.

## 13. Extension Points

| Extension | How |
|---|---|
| **MCP server** | Wrap `planner`, `nutrition`, `substitutes` and pantry CRUD as MCP tools (`get_pantry`, `update_pantry`, `lookup_nutrition`, `calculate_macros`, `suggest_substitutes`, `recommend_meal`). The core has no UI dependencies, so this is a thin wrapper. |
| **Telegram bot** | Another front end calling `planner.recommend`. |
| **Model swap** | Change `MODEL_NAME` in `config.py`. |
| **Feedback learning** | Use `cooked_log.rating_tags` as few-shot context; later, as fine-tuning data. |
| **More diets** | Add a rule function in `filters.py` and a gap profile in `gaps.py`. |
| **Skills.md** | Optional file that teaches an MCP agent the flavor-role rules and the 10% macro tolerance. |
