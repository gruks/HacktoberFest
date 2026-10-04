"""Target calculation for BMR, TDEE, calories, and protein."""
from pantrypal.models import Profile, TargetMacros

# Activity level factors
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.20,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
}

# Goal calorie adjustments
GOAL_MULTIPLIERS = {
    "lose": 0.85,       # -15%
    "maintain": 1.00,   # 0%
    "gain": 1.10,       # +10%
}

# Base protein factors in g/kg
PROTEIN_BASE_RATES = {
    "lose": 2.0,
    "maintain": 1.8,
    "gain": 1.8,
}


def calculate_bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Calculate Basal Metabolic Rate using the Mifflin-St Jeor equation."""
    sex_clean = sex.strip().lower()
    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    if sex_clean == "male":
        return base + 5.0
    elif sex_clean == "female":
        return base - 161.0
    else:
        raise ValueError(f"Unsupported sex: {sex}")


def calculate_tdee(bmr: float, activity: str) -> float:
    """Calculate Total Daily Energy Expenditure from BMR and activity level."""
    mult = ACTIVITY_MULTIPLIERS.get(activity.strip().lower())
    if mult is None:
        raise ValueError(f"Unknown activity level: {activity}")
    return bmr * mult


def calculate_protein_target(weight_kg: float, goal: str, diet_mode: str) -> float:
    """
    Calculate daily protein target in grams:
    Base: lose 2.0, maintain 1.8, gain 1.8 g/kg.
    Carnivore mode: +0.2 g/kg, capped at 2.2 g/kg.
    """
    rate = PROTEIN_BASE_RATES.get(goal.strip().lower(), 1.8)
    if diet_mode.strip().lower() == "high_protein_carnivore":
        rate += 0.2
    rate = min(rate, 2.2)
    return round(weight_kg * rate, 1)


def compute_targets(profile: Profile) -> TargetMacros:
    """
    Compute daily and per-meal targets:
    1. BMR via Mifflin-St Jeor
    2. TDEE = BMR * activity factor
    3. Daily kcal = max(TDEE * goal multiplier, BMR) (never below BMR)
    4. Daily protein = weight_kg * rate
    5. Per-meal targets = daily / meals_per_day
    """
    bmr = calculate_bmr(profile.sex, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calculate_tdee(bmr, profile.activity)
    
    goal_mult = GOAL_MULTIPLIERS.get(profile.goal.strip().lower(), 1.0)
    raw_daily_kcal = tdee * goal_mult
    
    # Cap deficit: daily kcal never falls below BMR
    daily_kcal = max(raw_daily_kcal, bmr)
    daily_protein = calculate_protein_target(profile.weight_kg, profile.goal, profile.diet_mode)
    
    meals_count = max(1, profile.meals_per_day)
    meal_kcal = round(daily_kcal / meals_count, 1)
    meal_protein = round(daily_protein / meals_count, 1)

    return TargetMacros(
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        daily_kcal=round(daily_kcal, 1),
        daily_protein_g=daily_protein,
        meal_kcal=meal_kcal,
        meal_protein_g=meal_protein,
    )
