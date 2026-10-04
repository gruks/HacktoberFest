# PantryPal: 1-Day Build Plan

**Total:** about 11-12 focused hours. Each block ends with a checkpoint you can verify. If a block runs over, use the cut list at the bottom.

**Rule for the day:** the deterministic core ships first. The LLM is the last layer, not the first.

---

## Before you start (30 min, night before if possible)

- [ ] Install Ollama, then `ollama pull qwen3:4b` and `ollama pull nomic-embed-text`
- [ ] Python 3.10+, create the venv, `pip install streamlit pydantic ollama pytest`
- [ ] Create the GitHub repo and drop in `README.md`, `PRD.md`, `ARCHITECTURE.md`
- [ ] Ask your friend: cuisine, which meals, height/weight/goal, which utensils, 10 favourite dishes
- [ ] Get a free USDA FoodData Central API key (optional, for the nutrition script)

---

## Block 1: Foundation (09:00-10:30, 1.5 h)

**Build**
- Folder structure from ARCHITECTURE.md §3
- `config.py`, `models.py` (Pydantic: Profile, Ingredient, Recipe, Plan)
- `db.py`: create tables, CRUD for profile, utensils, pantry
- `targets.py`: BMR, TDEE, kcal and protein targets, per-meal split

**Checkpoint**
- `pytest tests/test_targets.py` passes with one hand-checked example
- You can save and load a profile from Python

---

## Block 2: Nutrition data (10:30-12:30, 2 h)

This is the longest manual step. Keep the dataset small.

**Build**
- `data/nutrition.json` with **~80 ingredients** relevant to your friend's cooking: proteins (chicken, mince, eggs, fish, paneer if relevant), vegetables, staples, oils, dairy, a few carbs
- Per 100 g: kcal, protein, carbs, fat, fiber, sugar, plus the 10 micros
- Tag each with `animal_based` and `flavor_roles`
- `data/units.json` (egg ≈ 50 g, onion ≈ 110 g, tbsp oil ≈ 14 g, etc.) and `data/daily_values.json`
- `units.py` and `nutrition.py`: sum macros and micros, apply cooking factors

**Shortcut:** write `scripts/build_nutrition.py` to pull values from USDA FDC for a list of names, cache to JSON, then hand-fix mistakes. Do not parse the full dataset.

**Checkpoint**
- Calculate one recipe by hand, compare to the code, and confirm the difference is under 1%
- `test_nutrition.py` passes

---

## Lunch (12:30-13:15)

---

## Block 3: Recipes, filters, scoring, scaling (13:15-15:15, 2 h)

**Build**
- `data/recipes.json` with **30 recipes**:
  - 10+ carnivore-compatible (eggs, mince, steak, chicken thigh, fish, liver, bacon)
  - 15+ light-oil healthy
  - at least 8 that work in an air fryer or microwave
- `filters.py`: utensil alternatives and diet-mode rules
- `scoring.py`: coverage and ranking
- `scaling.py`: scale factor with clamp, carnivore fat-to-protein logic
- `gaps.py` and `shopping.py`
- `planner.py` v1: filter → rank → scale → nutrition → shopping list, **no LLM**

**Checkpoint**
- From a Python shell, with a sample pantry, `recommend()` returns 5 sensible plans
- A recipe needing an oven never appears when no oven is owned
- Carnivore mode never returns a plant-based recipe
- Tests: filters, scaling

> At this point you have a working, useful product. Everything after this is enhancement.

---

## Block 4: Streamlit UI (15:15-17:00, 1.75 h)

**Build**
- `app.py` with four tabs: **Profile**, **Kitchen**, **Cook**, **Shopping**
- Pantry editor (`st.data_editor` works well), utensil checkboxes
- Recipe cards with ingredient status, grams, macros table, micro progress bars, gap warnings
- "I cooked this" button that deducts from the pantry

**Checkpoint**
- Enter your friend's real pantry, press **What can I cook?**, and get a usable answer in the browser
- Open it from your phone over LAN

---

## Break (17:00-17:30)

---

## Block 5: LLM layer (17:30-19:30, 2 h)

**Build**
- `llm.py`: Ollama client, JSON schemas for Call A (pick substitute) and Call B (rewrite steps), timeout, one retry, fallback to `None`
- `substitutions.json`: flavor-role table, about 10 roles with 3-5 options each
- `substitutes.py`: candidate filtering, model pick, verify loop (max 3 attempts, 10% tolerance)
- Wire into `planner.py` step 5 and show "swapped X → Y because ..." in the UI
- Optional: show a spinner and render ranked results first, then fill in LLM results

**Checkpoint**
- A recipe missing lemon juice and with vinegar in the pantry shows a valid swap and still lands within 10% on macros
- Stop Ollama and confirm the app still works with a banner
- A mocked bad model answer is rejected in `test_substitutes.py`

---

## Block 6: Validate with the real person (19:30-20:30, 1 h)

- Have your friend try it, ideally while he cooks something that evening
- Record: a screen recording or video, and **his exact words** (the challenge's bonus points)
- Note anything that confused him and fix one quick issue

---

## Block 7: Ship (20:30-22:00, 1.5 h)

- [ ] Run `pytest -q` and fix failures
- [ ] Spot-check macros for 5 recipes against a calculator
- [ ] Update README with real screenshots and the friend's quote
- [ ] Record a 2-minute demo: profile → pantry → recommend → substitution → shopping list
- [ ] Push to GitHub, tag `v1.0`
- [ ] Write the DEV post using the template: What I Built, Demo, Code, How I Built It, Why Open Innovation Matters
- [ ] Add the tags `devchallenge`, `weekendchallenge`, `hf26challenge` and publish

---

## Cut list (drop in this order if behind)

1. MCP server (not scheduled; only do it with leftover time)
2. Feedback tags and cooked log analytics
3. Embedding-based candidate ranking (use the table order instead)
4. Step rewriting (Call B). Keep only substitution
5. Prices on the shopping list
6. Reduce recipes from 30 to 20 and ingredients from 80 to 60

**Never cut:** profile and targets, utensil and diet filters, nutrition math, scaling, shopping list, and the UI. They are the product.

---

## Time-saving tips

- Write the nutrition data and recipes in a text editor with a template. Don't build an admin UI for them.
- Use `qwen3:4b` with thinking disabled. Thinking mode burns tokens and time on a 1650.
- Keep prompts short and always pass a schema.
- Test the LLM in a standalone script first, before wiring it in.
- Commit at the end of every block so you can always roll back.

---

## Demo script (2 min)

1. **0:00** The problem: "My friend never has the full ingredient list."
2. **0:15** Show the profile and utensils; the targets appear.
3. **0:30** Show his real pantry.
4. **0:45** Press *What can I cook?* and show the ranked results.
5. **1:05** Open a recipe: grams, macros, micros, gap flag.
6. **1:25** Show a substitution with the "why" and the macro check.
7. **1:40** Show the shopping list.
8. **1:50** Disconnect Wi-Fi and run it again. Close with his reaction.
