# 🥘 PantryPal

**A private, offline kitchen assistant that starts from what's in your pantry.**

Built for one real friend who lives in a flat, never has every ingredient, and follows either a light-oil healthy or a high-protein carnivore diet. PantryPal knows his utensils, his diet and his pantry, then tells him what to cook tonight, in exact grams, with macros, micros and a shopping list for any gaps.

Everything runs locally on a modest GPU (GTX 1650, 4 GB VRAM). No internet, no accounts, no data leaving the machine.

> Built for the Hacktoberfest Weekend Challenge: *Build for a Friend*.

---

## ✨ Features

- **Kitchen profile:** utensils (air fryer, microwave, stove, oven, ...) and diet mode
- **Pantry tracking:** add what you have, with quantities and units
- **"What can I cook?":** ranked recipes that fit your utensils, diet and pantry
- **Exact portions:** grams per ingredient, scaled to your calorie and protein target
- **Smart substitutions:** missing something? A local LLM picks a replacement with the same flavor role, and code checks the macros stay within 10%
- **Macros and micros:** calories, protein, carbs, fat, fiber, plus key vitamins and minerals as % of daily value
- **Honest gap flags:** for example low vitamin C and fiber on carnivore
- **Shopping list:** only what's missing, with optional prices
- **Utensil-aware steps:** "pan-fry" becomes "air fry at 200 °C for 12 min"

## 🧠 How it works

| Layer | Does | Technology |
|---|---|---|
| **Code** | filtering, scoring, scaling, nutrition math | Python |
| **LLM** | picks substitutes, rewrites steps | Qwen3 4B via Ollama |
| **Data** | profile, pantry, recipes, nutrition | SQLite and JSON |
| **UI** | phone-friendly interface | Streamlit |

The model never calculates nutrition and never invents ingredients. It chooses from candidate lists that code prepares, and its output is validated against a strict JSON schema. If the model is offline, the app still works without substitutions and step rewrites.

See [ARCHITECTURE.md](ARCHITECTURE.md) for details and [PRD.md](PRD.md) for requirements.

## 🖥️ Requirements

- Python 3.10+
- [Ollama](https://ollama.com)
- A GPU with 4 GB+ VRAM (CPU-only works, just slower)
- About 4 GB free disk space for models

## 🚀 Quick start

```bash
# 1. Clone
git clone https://github.com/<your-username>/pantrypal.git
cd pantrypal

# 2. Python environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Pull the models (one-time, needs internet)
ollama pull qwen3:4b
ollama pull nomic-embed-text       # optional: better substitute ranking

# 4. Run
streamlit run app.py
```

Open `http://localhost:8501`.

**Use it from your phone:** run `streamlit run app.py --server.address 0.0.0.0`, then open `http://<laptop-ip>:8501` on the same Wi-Fi.

## 📖 Usage

1. **Profile:** pick your diet mode, enter age, height, weight, activity and goal. PantryPal shows your daily and per-meal targets.
2. **Kitchen:** tick your utensils and add pantry items.
3. **Cook:** press **What can I cook?** Expand a recipe to see:
   - ingredients split into *have* / *swapped* / *need to buy*
   - grams for your target
   - macros, micros and gap flags
   - steps for your equipment
4. **Shopping:** see everything you're missing in one list.
5. After cooking, press **I cooked this** to deduct the ingredients from your pantry.

## ⚙️ Configuration

Edit `pantrypal/config.py`:

| Setting | Default | Meaning |
|---|---|---|
| `MODEL_NAME` | `qwen3:4b` | Swap for `qwen2.5:3b-instruct` or `llama3.2:3b` |
| `MACRO_TOLERANCE` | `0.10` | Max kcal/protein drift allowed for a substitution |
| `SCALE_MIN` / `SCALE_MAX` | `0.5` / `2.5` | Portion scaling limits |
| `TOP_K` | `5` | Recipes returned |
| `LLM_TIMEOUT_S` | `30` | Fallback to code-only after this |

## 📂 Project structure

```
pantrypal/
├── app.py                  Streamlit UI
├── pantrypal/              Core logic (no UI dependencies)
│   ├── targets.py          calorie and protein targets
│   ├── nutrition.py        macros, micros, cooking adjustments
│   ├── filters.py          utensil and diet rules
│   ├── scoring.py          pantry coverage and ranking
│   ├── scaling.py          portion scaling
│   ├── substitutes.py      candidates and macro verify loop
│   ├── llm.py              Ollama adapter with schemas and fallback
│   └── planner.py          end-to-end pipeline
├── data/                   nutrition, recipes, substitution tables
├── tests/                  unit tests (no model required)
└── scripts/                data-prep helpers
```

## 🧪 Tests

```bash
pytest -q
```

The core logic is tested without the LLM. Substitution tests use a mocked model.

## 🍽️ Adding your own recipes

Add an entry to `data/recipes.json`:

```json
{
  "id": "egg_mince_bowl",
  "name": "Egg and Mince Bowl",
  "carnivore_ok": true,
  "requires_any": [["stove"], ["microwave"]],
  "servings": 1,
  "method": "pan_fry",
  "ingredients": [
    {"id": "beef_mince_raw", "grams": 200, "role": "bulk_protein", "essential": true},
    {"id": "egg_whole",      "grams": 100, "role": "creaminess",   "essential": false}
  ],
  "steps": ["Brown the mince.", "Add the eggs and scramble."]
}
```

Make sure every `id` exists in `data/nutrition.json`. The test suite checks this.

## 🔓 Why open-source AI?

- **Private:** body stats, diet and pantry contents never leave the machine.
- **Offline:** works without internet once models are downloaded.
- **Free to run:** no API fees.
- **Swappable:** change the model with one config line.
- **Tunable:** prompts and examples can be adapted to one person's taste.

## ⚠️ Disclaimer

PantryPal is a cooking and meal-planning helper, **not medical or dietary advice**. Nutrient values are estimates. Cooking adjustments are approximations. If you have a medical condition, are pregnant, or are considering a restrictive diet such as carnivore, talk to a qualified professional.

## 🗺️ Roadmap

- [ ] MCP server exposing PantryPal tools to any MCP client
- [ ] Telegram bot front end
- [ ] Feedback tags that tune future substitutions
- [ ] Weekly planner with a combined shopping list
- [ ] More diets (vegetarian, high-fiber, low-sodium)

## 🙏 Credits

- Nutrition data: USDA FoodData Central and the Indian Food Composition Tables (IFCT 2017)
- Models: Qwen (Alibaba), served locally with Ollama
- Built for a friend. Thanks for being the beta tester. 🧡

## 📄 License

MIT
