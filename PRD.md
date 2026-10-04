# PantryPal: Product Requirements Document

**Version:** 1.0 (1-day build)
**Status:** Ready to build
**Challenge:** Hacktoberfest Weekend Challenge, *Build for a Friend*

---

## 1. Summary

PantryPal is a private, offline kitchen assistant. It knows what utensils a person owns, what diet they follow, and what ingredients they currently have. It then recommends what to cook tonight, with exact quantities, macros, micros, a shopping list for any gaps, and sensible substitutions for missing ingredients.

It is built for **one real person: a friend who lives in a flat and rarely has every ingredient a recipe asks for.** Recipes assume a full kitchen. His kitchen is partial and changes week to week.

## 2. Problem

| Pain | Detail |
|---|---|
| Recipes assume a full pantry | He usually lacks 1-3 ingredients and gives up or orders food. |
| Substitutes exist, but nobody tells him how to make them work | Generic "swap X for Y" advice ignores taste and macros. |
| Equipment is limited | Many recipes assume an oven or full stove; he has an air fryer and microwave. |
| He follows a specific diet | Either light-oil healthy meals or high-protein carnivore. Most recipe apps filter poorly for this. |
| Portion size is guesswork | He does not know how many grams he should cook to hit his targets. |
| Cloud apps want his data | Diet, body stats and pantry contents are personal. |

## 3. Target User

**Primary (and only) persona: "the flat-dweller friend."**

- Lives in a flat with a small kitchen
- Owns some of: air fryer, microwave, stove, kettle, maybe a pressure cooker
- Chooses between two eating modes: **light-oil healthy** or **high-protein carnivore**
- Comfortable with a phone or laptop, not with a terminal
- Wants an answer in under a minute, not a meal-planning project

## 4. Goals

1. Answer "what can I cook right now?" using only what he has, plus a clear list of what he'd need to buy.
2. Give **correct** macros and micros. Numbers come from code and a nutrition table, never from the language model.
3. Scale quantities in grams to his daily calorie and protein target.
4. Respect his utensils and diet mode as hard constraints.
5. Suggest substitutions that preserve flavor role and stay within a macro tolerance.
6. Run entirely on a **GTX 1650 (4 GB VRAM)** with **no internet at runtime**.
7. Be handed to the friend and used for at least one real meal.

## 5. Non-Goals

- Not a medical or clinical nutrition tool. No diagnosis, no treatment advice.
- No live grocery prices, store availability or delivery integration (prices are user-entered).
- No free-form recipe invention by the model in v1. Recipes come from a curated library.
- No multi-user accounts, login or cloud sync.
- No barcode scanning or photo recognition.
- No weekly meal planning in v1 (single-meal recommendation only).

## 6. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-1 | user | set my diet mode, body stats and goal once | targets are computed for me |
| US-2 | user | tick the utensils I own | I never get a recipe I can't cook |
| US-3 | user | add, edit and remove pantry items with quantities | recommendations reflect reality |
| US-4 | user | tap "What can I cook?" and get ranked recipes | I can pick quickly |
| US-5 | user | see which ingredients I have vs. need to buy | I know whether it's worth it |
| US-6 | user | see exact grams per ingredient for my target | I cook the right amount |
| US-7 | user | see macros and micros for the meal | I know what I'm eating |
| US-8 | user | get a substitution when one ingredient is missing | I can cook now instead of shopping |
| US-9 | user | see steps rewritten for my air fryer or microwave | the recipe works in my kitchen |
| US-10 | user | be told honestly about nutrient gaps in my diet mode | I can compensate |
| US-11 | user | mark a meal as cooked | the pantry updates automatically |
| US-12 | user | give quick feedback ("too bland", "needs heat") | the app improves over time (stretch) |

## 7. Functional Requirements

### 7.1 Profile and targets (MUST)
- **FR-1** Store: diet mode, sex, age, height (cm), weight (kg), activity level, goal (lose / maintain / gain), meals per day.
- **FR-2** Compute daily calories with Mifflin-St Jeor times an activity factor, adjusted by goal (lose −15%, maintain 0%, gain +10%).
- **FR-3** Compute a daily protein target: 1.6-2.2 g/kg depending on mode and goal.
- **FR-4** Derive a per-meal target by dividing daily targets by meals per day.

### 7.2 Utensils (MUST)
- **FR-5** Store a set of owned utensils from a fixed list (stove, microwave, air fryer, oven, pressure cooker, rice cooker, kettle).
- **FR-6** Recipes declare required utensils. Any recipe whose requirements he doesn't meet is excluded.

### 7.3 Pantry (MUST)
- **FR-7** CRUD pantry items: name (from the nutrition table), quantity, unit (g, ml, pieces).
- **FR-8** Support unit conversion for common pieces (egg ≈ 50 g, onion ≈ 110 g, etc.) via a conversion table.
- **FR-9** Staples (salt, pepper, water, basic spices) can be flagged "always available."

### 7.4 Recommendation (MUST)
- **FR-10** Hard filters: utensils and diet-mode compatibility.
- **FR-11** Score remaining recipes by pantry coverage (% of calorie-weighted ingredient mass available).
- **FR-12** Return the top N (default 5) with coverage, missing items and a one-line fit summary.
- **FR-13** Recipes with ≥1 missing ingredient attempt substitution (7.5) before being marked "need to buy."

### 7.5 Substitution (MUST)
- **FR-14** Candidate substitutes come from a curated substitution table keyed by **flavor role** (acid, fat, umami, heat, sweet, crunch, creaminess, bulk protein, starch).
- **FR-15** Code pre-filters candidates to those in the pantry and compatible with the diet mode. Max 8 candidates are sent to the model.
- **FR-16** The model picks one candidate and justifies it in one sentence, returned as strict JSON.
- **FR-17** Code recomputes macros after substitution. If calories or protein drift more than **10%** from the original, the quantity is rebalanced in code (up to 3 attempts). Otherwise the substitution is rejected.

### 7.6 Portioning (MUST)
- **FR-18** Scale all ingredient grams by `meal_target_kcal / recipe_kcal`, clamped to a 0.5x-2.5x range, with a warning outside that range.
- **FR-19** In carnivore mode, scale only animal ingredients and preserve a fat-to-protein ratio between 0.8:1 and 1.2:1 by weight, where possible.
- **FR-20** Display final quantities in grams, with a friendly unit alongside when known (for example "2 eggs (100 g)").

### 7.7 Nutrition output (MUST)
- **FR-21** Show macros: kcal, protein, carbs, fat, fiber, and sugar.
- **FR-22** Show micros: sodium, potassium, calcium, iron, magnesium, zinc, vitamin A, vitamin C, vitamin D, vitamin B12 (v1 set), each as a % of daily value.
- **FR-23** Apply cooking adjustments: added oil per method (air fry, pan fry, microwave, boil) and optional retention factors.
- **FR-24** Flag diet-mode nutrient gaps with plain wording (for example carnivore: low vitamin C and fiber).

### 7.8 Shopping list (MUST)
- **FR-25** List only missing ingredients, with quantity needed after scaling.
- **FR-26** Optional user-entered price per item. The total is shown if prices exist.

### 7.9 Step rewriting (SHOULD)
- **FR-27** The model rewrites generic steps for his available utensils, returning JSON (`steps[]` with time and temperature).
- **FR-28** Time and temperature values are validated against sane ranges in code before display.

### 7.10 Cook and update (SHOULD)
- **FR-29** "I cooked this" subtracts used quantities from the pantry.

### 7.11 Feedback (COULD)
- **FR-30** Store taste feedback tags per recipe and use them as extra context for future substitutions.

### 7.12 Interface (MUST)
- **FR-31** A Streamlit web UI with four screens: Profile, Kitchen (utensils + pantry), Cook, Shopping list. Must be usable on a phone browser on the same Wi-Fi.

### 7.13 Interface (COULD)
- **FR-32** MCP server exposing the core tools.

## 8. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Runs on GTX 1650, 4 GB VRAM | Model ≤ 2.6 GB loaded |
| NFR-2 | Offline at runtime | Zero network calls after setup |
| NFR-3 | Response time for "What can I cook?" | < 3 s for ranking; < 20 s including model steps |
| NFR-4 | Nutrition correctness | 100% of numbers from code |
| NFR-5 | Model output validity | Schema-constrained; invalid output retried once, then falls back to code-only |
| NFR-6 | Privacy | All data stored in a local SQLite file; no telemetry |
| NFR-7 | Graceful degradation | If Ollama is down, the app still works without substitutions and rewrites |
| NFR-8 | Testability | Core logic covered by unit tests, with no model required |

## 9. Success Metrics

**For the challenge**
- The friend cooks at least one full meal with the app and gives a quote.
- A working demo video (2 minutes).
- Public repo with README, PRD and architecture docs.

**For the product**
- At least 70% of recommended recipes have ≥ 80% pantry coverage after substitution on his real pantry.
- Macro error vs. hand calculation is under 3% on 5 spot-checked recipes.
- No recipe is shown that needs a utensil he doesn't own.

## 10. Scope for the 1-Day Build

| Priority | Items |
|---|---|
| **MUST** | Profile and targets, utensils, pantry, recipe filter and ranking, scaling, macros and micros, shopping list, Streamlit UI, 30 recipes, ~80 ingredients |
| **SHOULD** | LLM substitutions with verify loop, LLM step rewriting, "I cooked this" |
| **COULD** | Feedback tags, MCP server, Telegram bot, price memory |
| **WON'T (v1)** | Weekly planner, recipe generation, grocery APIs |

**Cut order if time runs short:** MCP → feedback → step rewriting → substitution polish. The deterministic core must ship.

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 4B model gives poor or invalid JSON | Broken substitutions | Strict JSON schema, one retry, code-only fallback |
| Nutrition data entry takes too long | Blows the schedule | Seed only ~80 ingredients; pull from USDA once via a script; hand-fix the rest |
| Carnivore mode produces thin recipe variety | Weak demo | Write at least 10 carnivore-compatible recipes (eggs, mince, steak, chicken thigh, fish, liver, bacon) |
| Unit conversions are wrong (pieces vs. grams) | Wrong macros | Single conversion table, unit tests |
| Model hallucinates a substitute not in the pantry | Bad advice | Model can only choose from a code-provided candidate list; any other answer is rejected |
| Health misuse of carnivore mode | Safety concern | Neutral gap flags and a visible "not medical advice" note |
| GPU memory pressure | Slow or crashing | Context under 1.5k tokens, one model loaded at a time, embeddings on CPU |

## 12. Why Open-Source AI Is Essential

- **Privacy:** diet, body stats and pantry never leave the machine.
- **Offline:** works with no internet once models and data are downloaded.
- **Zero running cost:** no per-request fees.
- **Swappable:** the model can be changed (Qwen3 4B, Llama 3.2 3B, Gemma 3 4B) without touching application code.
- **Tunable:** prompts and few-shot examples can be adjusted to the friend's taste, and feedback can later inform fine-tuning.

## 13. Open Questions

1. Does the friend cook mainly Indian food? (Decides whether to prioritize IFCT values for ingredients.)
2. Which meals matter most: lunch, dinner or both?
3. Does he want prices at all, or just a "what to buy" list?
4. Is the vegetarian filter needed in "healthy" mode?
