"""Pydantic data models for PantryPal."""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class Profile(BaseModel):
    """User profile for BMR/TDEE and macro target calculation."""
    sex: str = Field(..., description="'male' or 'female'")
    age: int = Field(..., ge=1, le=120)
    height_cm: float = Field(..., ge=50, le=250)
    weight_kg: float = Field(..., ge=20, le=300)
    activity: str = Field(..., description="'sedentary', 'light', 'moderate', 'active'")
    goal: str = Field(..., description="'lose', 'maintain', 'gain'")
    diet_mode: str = Field(..., description="'light_oil_healthy' or 'high_protein_carnivore'")
    meals_per_day: int = Field(default=3, ge=1, le=8)

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"male", "female"}:
            raise ValueError("sex must be 'male' or 'female'")
        return v_clean

    @field_validator("activity")
    @classmethod
    def validate_activity(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"sedentary", "light", "moderate", "active"}:
            raise ValueError("activity must be 'sedentary', 'light', 'moderate', or 'active'")
        return v_clean

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"lose", "maintain", "gain"}:
            raise ValueError("goal must be 'lose', 'maintain', or 'gain'")
        return v_clean

    @field_validator("diet_mode")
    @classmethod
    def validate_diet(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean not in {"light_oil_healthy", "high_protein_carnivore"}:
            raise ValueError("diet_mode must be 'light_oil_healthy' or 'high_protein_carnivore'")
        return v_clean


class TargetMacros(BaseModel):
    """Calculated calorie and protein targets."""
    bmr: float
    tdee: float
    daily_kcal: float
    daily_protein_g: float
    meal_kcal: float
    meal_protein_g: float


class NutritionInfo(BaseModel):
    """Macros and micronutrients per serving or per meal."""
    kcal: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fiber: float = 0.0
    sugar: float = 0.0
    micros: Dict[str, float] = Field(default_factory=dict)


class IngredientItem(BaseModel):
    """Ingredient reference in a recipe."""
    id: str
    grams: float
    role: str
    essential: bool = False
    name: Optional[str] = None


class Recipe(BaseModel):
    """Recipe definition."""
    id: str
    name: str
    diet_tags: List[str] = Field(default_factory=list)
    carnivore_ok: bool = False
    requires_any: List[List[str]] = Field(default_factory=list)
    servings: int = 1
    method: str = "pan_fry"
    ingredients: List[IngredientItem] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)


class SubstitutionChoice(BaseModel):
    """Substitution result for a missing ingredient."""
    original_id: str
    substitute_id: str
    ratio: float = 1.0
    reason: str = ""
    taste_note: str = ""


class ShoppingItem(BaseModel):
    """Shortfall item on the shopping list."""
    id: str
    name: str
    shortfall_grams: float
    friendly_quantity: str = ""
    price_est: Optional[float] = None


class StepItem(BaseModel):
    """Rewritten cooking step with structured parameters."""
    text: str
    minutes: Optional[int] = None
    temp_c: Optional[int] = None


class Plan(BaseModel):
    """Complete recommendation plan for a recipe."""
    recipe: Recipe
    scale: float
    coverage: float
    missing: List[IngredientItem] = Field(default_factory=list)
    swapped: List[SubstitutionChoice] = Field(default_factory=list)
    final_nutrition: NutritionInfo
    gaps: List[str] = Field(default_factory=list)
    shopping_list: List[ShoppingItem] = Field(default_factory=list)
    final_steps: List[StepItem] = Field(default_factory=list)
