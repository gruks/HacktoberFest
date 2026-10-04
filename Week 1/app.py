"""PantryPal: Private, offline kitchen assistant.
Streamlit application interface.
"""
import sys
from pathlib import Path

# Ensure application directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from pantrypal.config import ALL_UTENSILS
from pantrypal.db import (
    deduct_pantry_items,
    delete_pantry_item,
    get_cooked_log,
    get_pantry,
    get_profile,
    get_utensils,
    init_db,
    log_cooked,
    save_profile,
    set_pantry_item,
    set_utensils,
)
from pantrypal.llm import is_ollama_available
from pantrypal.models import Profile
from pantrypal.nutrition import (
    calculate_micro_percentages,
    get_ingredient_nutrition,
    load_nutrition_db,
)
from pantrypal.planner import recommend
from pantrypal.targets import compute_targets
from pantrypal.units import (
    convert_to_grams,
    format_friendly_quantity,
    get_available_units,
    is_staple,
)

# Set page configuration
st.set_page_config(
    page_title="PantryPal - Offline Kitchen Assistant",
    page_icon="🥘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database
init_db()

# --- Sidebar: Offline Status & Navigation Context ---
with st.sidebar:
    st.title("🥘 PantryPal")
    st.caption("100% Private & Offline Kitchen Assistant")
    st.divider()

    ollama_online = is_ollama_available()
    if ollama_online:
        st.success("🟢 Local AI Engine Active (Ollama qwen3-vl:4b)")
    else:
        st.warning("⚪ Local AI Offline (Code Heuristics Mode)")

    st.divider()

    profile_data = get_profile()
    owned_utensils = get_utensils()
    pantry_data = get_pantry()

    if profile_data:
        targets_info = compute_targets(profile_data)
        st.subheader("🎯 Active Targets")
        st.markdown(f"**Diet:** `{profile_data.diet_mode}`")
        st.markdown(f"**Daily:** `{targets_info.daily_kcal} kcal` | `{targets_info.daily_protein_g}g protein`")
        st.markdown(f"**Per Meal ({profile_data.meals_per_day}/day):** `{targets_info.meal_kcal} kcal` | `{targets_info.meal_protein_g}g protein`")
    else:
        st.info("⚠️ Complete your profile to calculate meal targets.")

    st.divider()
    st.caption(f"🍳 **Utensils Owned:** {len(owned_utensils)}")
    st.caption(f"📦 **Pantry Items:** {len(pantry_data)}")
    st.caption("🔒 **System:** Local SQLite, zero runtime telemetry.")

# --- Tab Layout ---
tab_profile, tab_kitchen, tab_cook, tab_shopping = st.tabs(
    ["👤 Profile & Targets", "🍳 Kitchen & Pantry", "🍽️ What Can I Cook?", "🛒 Shopping List"]
)

# ==============================================================================
# TAB 1: PROFILE & TARGETS
# ==============================================================================
with tab_profile:
    st.header("👤 Your Body & Dietary Goals")
    st.write("Calculates exact daily calorie expenditure (Mifflin-St Jeor) and target protein splits.")

    curr_p = profile_data or Profile(
        sex="male",
        age=28,
        height_cm=175.0,
        weight_kg=75.0,
        activity="light",
        goal="lose",
        diet_mode="light_oil_healthy",
        meals_per_day=3,
    )

    with st.form("profile_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            p_sex = st.selectbox("Biological Sex", options=["male", "female"], index=0 if curr_p.sex == "male" else 1)
            p_age = st.number_input("Age (years)", min_value=16, max_value=100, value=curr_p.age, step=1)
            p_height = st.number_input("Height (cm)", min_value=100.0, max_value=230.0, value=float(curr_p.height_cm), step=0.5)

        with col2:
            p_weight = st.number_input("Weight (kg)", min_value=35.0, max_value=250.0, value=float(curr_p.weight_kg), step=0.5)
            p_activity = st.selectbox(
                "Activity Level",
                options=["sedentary", "light", "moderate", "active"],
                index=["sedentary", "light", "moderate", "active"].index(curr_p.activity),
                help="sedentary (1.2x), light (1.375x), moderate (1.55x), active (1.725x)",
            )
            p_goal = st.selectbox(
                "Target Goal",
                options=["lose", "maintain", "gain"],
                index=["lose", "maintain", "gain"].index(curr_p.goal),
                help="lose (-15% kcal, higher protein), maintain (0%), gain (+10%)",
            )

        with col3:
            p_diet = st.selectbox(
                "Diet Mode",
                options=["light_oil_healthy", "high_protein_carnivore"],
                index=0 if curr_p.diet_mode == "light_oil_healthy" else 1,
                help="light_oil_healthy (low oil, diverse whole foods) | high_protein_carnivore (animal-based only, 0.8-1.2 fat:protein ratio)",
            )
            p_meals = st.number_input("Meals per Day", min_value=1, max_value=6, value=curr_p.meals_per_day, step=1)

        submitted = st.form_submit_button("💾 Save Profile & Update Targets", use_container_width=True)
        if submitted:
            new_profile = Profile(
                sex=p_sex,
                age=int(p_age),
                height_cm=float(p_height),
                weight_kg=float(p_weight),
                activity=p_activity,
                goal=p_goal,
                diet_mode=p_diet,
                meals_per_day=int(p_meals),
            )
            save_profile(new_profile)
            st.success("✅ Profile successfully updated and stored in local database!")
            st.rerun()

    # Live Target Preview Cards
    if profile_data:
        t = compute_targets(profile_data)
        st.subheader("📊 Computed Nutritional Target Breakdown")
        mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
        mcol1.metric("BMR", f"{t.bmr} kcal")
        mcol2.metric("TDEE", f"{t.tdee} kcal")
        mcol3.metric("Daily Target", f"{t.daily_kcal} kcal")
        mcol4.metric("Daily Protein", f"{t.daily_protein_g} g")
        mcol5.metric("Per-Meal Target", f"{t.meal_kcal} kcal")
        mcol6.metric("Per-Meal Protein", f"{t.meal_protein_g} g")

        st.caption(
            "ℹ️ Daily deficit is strictly constrained so that target calories never drop below Basal Metabolic Rate (BMR)."
        )

# ==============================================================================
# TAB 2: KITCHEN & PANTRY
# ==============================================================================
with tab_kitchen:
    st.header("🍳 Kitchen Utensils & Pantry Inventory")

    # --- Section A: Utensils ---
    st.subheader("1. Utensils You Own")
    st.write("Recipes requiring equipment not selected here will be excluded.")

    selected_utensils = []
    u_cols = st.columns(len(ALL_UTENSILS))
    for i, u_name in enumerate(ALL_UTENSILS):
        with u_cols[i]:
            display_title = u_name.replace("_", " ").title()
            is_checked = u_name in owned_utensils
            if st.checkbox(display_title, value=is_checked, key=f"u_{u_name}"):
                selected_utensils.append(u_name)

    if set(selected_utensils) != owned_utensils:
        if st.button("💾 Save Owned Utensils"):
            set_utensils(selected_utensils)
            st.success("Utensils updated!")
            st.rerun()

    st.divider()

    # --- Section B: Pantry Inventory ---
    st.subheader("2. Pantry Inventory")
    nutrition_db = load_nutrition_db()
    sorted_ingredients = sorted(
        nutrition_db.keys(),
        key=lambda k: nutrition_db[k].get("name", k),
    )

    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.write("##### ➕ Add / Update Item")
        chosen_ing_id = st.selectbox(
            "Select Ingredient",
            options=sorted_ingredients,
            format_func=lambda k: f"{nutrition_db[k].get('name', k)} ({nutrition_db[k].get('category', '')})",
        )

        avail_units = get_available_units(chosen_ing_id)
        u_col, q_col = st.columns(2)
        with u_col:
            chosen_unit = st.selectbox("Unit", options=avail_units)
        with q_col:
            input_qty = st.number_input("Quantity", min_value=0.1, value=1.0 if chosen_unit != "grams" else 200.0, step=1.0)

        is_item_staple_default = is_staple(chosen_ing_id)
        chosen_staple = st.checkbox(
            "Always Available (Staple)",
            value=is_item_staple_default,
            help="Staples (salt, pepper, spices) are considered always in stock and never deducted.",
        )
        chosen_price = st.number_input(
            "Price per 100g (optional, $)",
            min_value=0.0,
            value=0.0,
            step=0.25,
            format="%.2f",
        )

        if st.button("➕ Add to Pantry", use_container_width=True):
            grams_computed = convert_to_grams(chosen_ing_id, input_qty, chosen_unit)
            set_pantry_item(
                ingredient_id=chosen_ing_id,
                quantity_g=grams_computed,
                always_have=chosen_staple,
                price_per_100g=chosen_price if chosen_price > 0 else None,
            )
            st.success(f"Added {format_friendly_quantity(chosen_ing_id, grams_computed)} to pantry!")
            st.rerun()

        st.write("---")
        # Quick-load starter pantry button
        if st.button("📦 Load Starter Flat Pantry", help="Populates common ingredients: chicken, eggs, garlic, oil, vinegar, etc."):
            starter_items = [
                ("chicken_thigh_raw", 500.0, False, 1.20),
                ("egg_whole", 300.0, False, 0.60),  # 6 eggs
                ("olive_oil", 250.0, False, 1.50),
                ("garlic", 30.0, False, 0.80),
                ("vinegar", 200.0, False, 0.40),    # Useful for acid substitution
                ("salmon_raw", 300.0, False, 2.50),
                ("butter", 200.0, False, 1.00),
                ("broccoli_raw", 300.0, False, 0.40),
                ("salt", 500.0, True, None),
                ("black_pepper", 100.0, True, None),
            ]
            for i_id, qty, stp, prc in starter_items:
                set_pantry_item(i_id, qty, always_have=stp, price_per_100g=prc)
            st.success("Starter pantry loaded!")
            st.rerun()

    with col_list:
        st.write("##### 📦 Current Inventory")
        if not pantry_data:
            st.info("Pantry is empty. Add ingredients above or load starter pantry.")
        else:
            for ing_id, details in sorted(pantry_data.items()):
                nutr = nutrition_db.get(ing_id, {})
                ing_name = nutr.get("name", ing_id)
                friendly_qty = format_friendly_quantity(ing_id, details["quantity_g"])
                staple_badge = "🧂 Staple" if details["always_have"] else ""
                price_badge = f"${details['price_per_100g']:.2f}/100g" if details["price_per_100g"] else ""

                r_col1, r_col2, r_col3, r_col4 = st.columns([3, 2, 2, 1])
                with r_col1:
                    st.markdown(f"**{ing_name}**")
                with r_col2:
                    st.write(friendly_qty)
                with r_col3:
                    st.caption(f"{staple_badge} {price_badge}")
                with r_col4:
                    if st.button("🗑️", key=f"del_{ing_id}", help="Remove item"):
                        delete_pantry_item(ing_id)
                        st.rerun()

# ==============================================================================
# TAB 3: COOK ("WHAT CAN I COOK TONIGHT?")
# ==============================================================================
with tab_cook:
    st.header("🍽️ Meal Recommendation Engine")

    if not profile_data:
        st.warning("⚠️ Please save your Profile first in the 'Profile & Targets' tab.")
    elif not owned_utensils:
        st.warning("⚠️ Please select your available utensils in the 'Kitchen & Pantry' tab.")
    else:
        c_col1, c_col2 = st.columns([3, 1])
        with c_col1:
            cook_btn = st.button("🍳 What can I cook tonight?", type="primary", use_container_width=True)
        with c_col2:
            enable_step_rewrites = st.checkbox("Rewrite steps with AI", value=ollama_online, disabled=not ollama_online)

        if cook_btn or "recommendations" in st.session_state:
            if cook_btn:
                with st.spinner("Analyzing pantry coverage, resolving substitutions, and verifying nutrition..."):
                    plans = recommend(
                        profile_data,
                        owned_utensils,
                        pantry_data,
                        top_k=5,
                        enable_llm_steps=enable_step_rewrites,
                    )
                    st.session_state["recommendations"] = plans

            plans = st.session_state.get("recommendations", [])

            if not plans:
                st.warning("No recipes matched your owned utensils and diet mode! Try enabling more utensils or checking your diet mode.")
            else:
                st.success(f"Found {len(plans)} matching recipes ranked by pantry availability and target calorie fit.")

                for idx, plan in enumerate(plans, 1):
                    rec = plan.recipe
                    cov_pct = int(plan.coverage * 100)
                    cov_color = "🟢" if cov_pct >= 80 else ("🟡" if cov_pct >= 50 else "🔴")

                    with st.expander(f"{cov_color} #{idx}: {rec.name} — {cov_pct}% Coverage (Scale: {plan.scale}x)", expanded=(idx == 1)):
                        # Header badges
                        col_h1, col_h2, col_h3 = st.columns(3)
                        col_h1.metric("Coverage Score", f"{cov_pct}%")
                        col_h2.metric("Portion Scale", f"{plan.scale}x")
                        col_h3.metric("Cooking Method", rec.method.replace("_", " ").title())

                        # Substitution Alerts
                        if plan.swapped:
                            st.write("---")
                            st.write("##### 🔄 Culinary Substitutions Applied")
                            for swap in plan.swapped:
                                orig_name = nutrition_db.get(swap.original_id, {}).get("name", swap.original_id)
                                sub_name = nutrition_db.get(swap.substitute_id, {}).get("name", swap.substitute_id)
                                st.info(
                                    f"✨ **Swapped `{orig_name}` → `{sub_name}`** (ratio: {swap.ratio}x)\n\n"
                                    f"• **Why:** {swap.reason}\n\n"
                                    f"• **Taste Note:** {swap.taste_note}\n\n"
                                    f"• **Macro Check:** Validated within ±10% calorie/protein drift."
                                )

                        st.write("---")

                        # Ingredients Breakdown
                        st.write("##### 🥗 Ingredients Breakdown")
                        ing_col1, ing_col2 = st.columns(2)

                        pantry_items_in_recipe = []
                        missing_items_in_recipe = []
                        for ing in rec.ingredients:
                            # Check if swapped
                            swap_match = next((s for s in plan.swapped if s.original_id == ing.id), None)
                            if swap_match:
                                sub_id = swap_match.substitute_id
                                sub_name = nutrition_db.get(sub_id, {}).get("name", sub_id)
                                orig_name = nutrition_db.get(ing.id, {}).get("name", ing.id)
                                friendly_sub = format_friendly_quantity(sub_id, ing.grams * plan.scale * swap_match.ratio)
                                pantry_items_in_recipe.append(f"🟡 **{sub_name}** (swapped for {orig_name}): {friendly_sub}")
                                continue

                            scaled_g = round(ing.grams * plan.scale, 1)
                            p_info = pantry_data.get(ing.id, {})
                            avail_g = float(p_info.get("quantity_g", 0.0))
                            is_st = is_staple(ing.id) or p_info.get("always_have", False)

                            ing_name = nutrition_db.get(ing.id, {}).get("name", ing.id)
                            friendly_str = format_friendly_quantity(ing.id, scaled_g)

                            if is_st or avail_g >= scaled_g:
                                pantry_items_in_recipe.append(f"🟢 **{ing_name}**: {friendly_str}")
                            else:
                                short_g = scaled_g - avail_g
                                short_friendly = format_friendly_quantity(ing.id, short_g)
                                missing_items_in_recipe.append(f"🔴 **{ing_name}**: need {short_friendly} (have {int(avail_g)}g)")

                        with ing_col1:
                            st.write("**In Pantry / Ready:**")
                            if pantry_items_in_recipe:
                                for item_text in pantry_items_in_recipe:
                                    st.markdown(item_text)
                            else:
                                st.caption("None available.")

                        with ing_col2:
                            st.write("**Missing / Shortfall:**")
                            if missing_items_in_recipe:
                                for item_text in missing_items_in_recipe:
                                    st.markdown(item_text)
                            else:
                                st.markdown("🎉 *All ingredients covered!*")

                        st.write("---")

                        # Nutrition Summary
                        st.write("##### 🔬 Meal Nutrition")
                        n = plan.final_nutrition
                        ncol1, ncol2, ncol3, ncol4, ncol5 = st.columns(5)
                        ncol1.metric("Calories", f"{n.kcal} kcal")
                        ncol2.metric("Protein", f"{n.protein} g")
                        ncol3.metric("Carbs", f"{n.carbs} g")
                        ncol4.metric("Fat", f"{n.fat} g")
                        ncol5.metric("Fiber", f"{n.fiber} g")

                        # Micronutrient Progress Bars
                        st.write("##### 🧬 Micronutrients (% of Pro-Rated Daily Target)")
                        micro_pcts = calculate_micro_percentages(n.micros, profile_data.meals_per_day)
                        m_row1 = st.columns(5)
                        m_row2 = st.columns(5)

                        micro_list = list(micro_pcts.items())
                        for m_idx, (m_key, m_val) in enumerate(micro_list[:5]):
                            with m_row1[m_idx]:
                                label = m_key.replace("_mg", "").replace("_ug", "").replace("vit_", "Vit ").upper()
                                st.caption(f"{label}: **{m_val}%**")
                                st.progress(min(1.0, max(0.0, m_val / 100.0)))

                        for m_idx, (m_key, m_val) in enumerate(micro_list[5:10]):
                            with m_row2[m_idx]:
                                label = m_key.replace("_mg", "").replace("_ug", "").replace("vit_", "Vit ").upper()
                                st.caption(f"{label}: **{m_val}%**")
                                st.progress(min(1.0, max(0.0, m_val / 100.0)))

                        # Nutrient Gaps Advisory
                        if plan.gaps:
                            st.write("---")
                            st.write("##### ⚠️ Dietary Notes & Gap Warnings")
                            for gap_msg in plan.gaps:
                                st.warning(f"ℹ️ {gap_msg}")

                        # Cooking Steps
                        st.write("---")
                        st.write("##### 🧑‍🍳 Instructions")
                        for s_idx, step in enumerate(plan.final_steps, 1):
                            time_temp = []
                            if step.minutes:
                                time_temp.append(f"⏱️ {step.minutes} mins")
                            if step.temp_c:
                                time_temp.append(f"🌡️ {step.temp_c}°C")
                            extra_str = f" *({', '.join(time_temp)})*" if time_temp else ""
                            st.markdown(f"**Step {s_idx}:** {step.text}{extra_str}")

                        # "I Cooked This" Action Button
                        st.write("---")
                        if st.button(f"✅ I Cooked This ({rec.name})", key=f"cook_{rec.id}_{idx}"):
                            # Deduct from pantry (using substituted ingredients if swapped)
                            deductions = []
                            for ing in rec.ingredients:
                                swap_m = next((s for s in plan.swapped if s.original_id == ing.id), None)
                                if swap_m:
                                    deductions.append((swap_m.substitute_id, round(ing.grams * plan.scale * swap_m.ratio, 1)))
                                else:
                                    deductions.append((ing.id, round(ing.grams * plan.scale, 1)))

                            deduct_pantry_items(deductions)
                            log_cooked(rec.id, plan.scale)
                            st.success(f"🎉 Logged '{rec.name}' as cooked! Deducted ingredients from your pantry.")
                            if "recommendations" in st.session_state:
                                del st.session_state["recommendations"]
                            st.rerun()

# ==============================================================================
# TAB 4: SHOPPING LIST
# ==============================================================================
with tab_shopping:
    st.header("🛒 Shopping List")
    st.write("Aggregated missing ingredients for your selected meals.")

    plans = st.session_state.get("recommendations", [])
    if not plans:
        st.info("💡 Run 'What can I cook tonight?' in the Cook tab to generate missing ingredient lists.")
    else:
        recipe_options = [f"#{idx} {p.recipe.name} ({int(p.coverage*100)}% coverage)" for idx, p in enumerate(plans, 1)]
        selected_plan_idx = st.selectbox("Select Meal to Shop For", options=range(len(plans)), format_func=lambda i: recipe_options[i])

        active_plan = plans[selected_plan_idx]
        shopping_items = active_plan.shopping_list

        if not shopping_items:
            st.success("🎉 You already have everything needed for this meal! No groceries required.")
        else:
            st.write(f"##### Missing Ingredients for **{active_plan.recipe.name}**")

            total_est_cost = 0.0
            has_pricing = False

            shop_data = []
            for item in shopping_items:
                cost_str = "—"
                if item.price_est is not None:
                    has_pricing = True
                    total_est_cost += item.price_est
                    cost_str = f"${item.price_est:.2f}"

                shop_data.append({
                    "Ingredient": item.name,
                    "Amount Needed": item.friendly_quantity,
                    "Shortfall (g)": f"{item.shortfall_grams}g",
                    "Estimated Cost": cost_str,
                })

            st.table(shop_data)

            if has_pricing:
                st.subheader(f"💰 Total Estimated Cost: **${total_est_cost:.2f}**")

            # Copyable text summary
            st.write("##### 📋 Copy / Export List")
            export_lines = [f"- {item.name}: {item.friendly_quantity}" for item in shopping_items]
            export_text = f"Grocery List for {active_plan.recipe.name}:\n" + "\n".join(export_lines)
            st.text_area("Plain Text", value=export_text, height=120)
