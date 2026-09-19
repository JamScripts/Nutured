"""Public, non-identifying discovery contracts and deterministic filtering."""
from dataclasses import dataclass, replace
from typing import Literal, Protocol
from urllib.parse import urlencode

AGE_BANDS = {"baby": (0, 11, "Under 1 year"), "1-2": (12, 35, "1–2 years"), "3-4": (36, 59, "3–4 years"), "5-7": (60, 95, "5–7 years")}
KINDS = {"activity": "Activities", "outing": "Outings"}
INTERESTS = {"animals": "Animals", "art": "Art & making", "nature": "Nature", "music": "Music", "stories": "Stories", "building": "Building"}
TIMES = {"15": "15 minutes", "30": "30 minutes", "60": "1 hour", "180": "3 hours"}
BUDGETS = {"0": "Free / supplies on hand", "10": "Up to $10", "25": "Up to $25", "50": "Up to $50"}
SETTINGS = {"indoor": "Indoor", "outdoor": "Outdoor"}
CATEGORIES = (
    ("play", "Play & Learn", "Little activities. Big discoveries.", "sprout", "mint"),
    ("gifts", "Gift Finder", "A little something to inspire play.", "gift", "peach"),
    ("outings", "Things to Do", "Small adventures, close to home.", "pin", "blue"),
    ("skills", "Milestones & Skills", "Explore through everyday play.", "blocks", "yellow"),
    ("rainy", "Rainy Day Rescue", "Indoor ideas for cozy days.", "cloud", "lilac"),
    ("birthday", "Birthday Ideas", "Make their day a little magical.", "cake", "pink"),
)
CATEGORY_LABELS = {key: label for key, label, *_ in CATEGORIES if key != "gifts"}

@dataclass(frozen=True)
class Activity:
    id: str
    slug: str
    title: str
    summary: str
    image: str
    image_alt: str
    age_min_months: int
    age_max_months: int
    kind: Literal["activity", "outing"]
    tags: tuple[str, ...]
    interests: tuple[str, ...]
    duration: int
    setting: Literal["indoor", "outdoor"]
    cost: int
    cost_basis: Literal["supplies", "admission for one adult and one child"]
    materials: tuple[str, ...]
    steps: tuple[str, ...]
    supervision: str
    currency: str = "USD"
    review_status: str = "development fixture — not professionally reviewed"

    @property
    def age_label(self):
        return f"{self.age_min_months}–{self.age_max_months} months"

@dataclass(frozen=True)
class KitPreview:
    id: str
    name: str
    summary: str
    image: str
    image_alt: str
    status: str = "Preview"
    # Future approved template options belong here; no product or checkout data.

@dataclass(frozen=True)
class ChildProfile:
    id: str
    owner_id: str
    nickname: str | None
    age_band: str
    interests: tuple[str, ...]
    setting: str = ""

@dataclass(frozen=True)
class SearchPreferences:
    q: str = ""
    age: str = ""
    kind: str = ""
    interests: tuple[str, ...] = ()
    time: str = ""
    budget: str = ""
    setting: str = ""
    category: str = ""
    submitted: bool = False

def parse_preferences(args) -> SearchPreferences:
    """Whitelist known options; never reflect private/unrecognized URL fields."""
    def option(key, choices):
        value = args.get(key, "")
        return value if value in choices else ""
    values = dict(q=args.get("q", "").strip()[:120], age=option("age", AGE_BANDS),
        kind=option("kind", KINDS), interests=tuple(k for k in INTERESTS if k in args.getlist("interests")),
        time=option("time", TIMES), budget=option("budget", BUDGETS),
        setting=option("setting", SETTINGS), category=option("category", CATEGORY_LABELS))
    return SearchPreferences(**values, submitted=args.get("find") == "1" or any(values.values()))

def preference_url(p: SearchPreferences, path="/", anchor="just-for-you") -> str:
    params = [(key, getattr(p, key)) for key in ("q", "age", "kind", "time", "budget", "setting", "category") if getattr(p, key)]
    params.extend(("interests", interest) for interest in p.interests)
    if p.submitted:
        params.append(("find", "1"))
    return path + ("?" + urlencode(params) if params else "") + ("#" + anchor if anchor else "")

def filter_activities(activities: tuple[Activity, ...], p: SearchPreferences) -> tuple[Activity, ...]:
    def matches(a):
        band = AGE_BANDS.get(p.age)
        return (not p.q or p.q.casefold() in " ".join((a.title, a.summary, *a.tags)).casefold()) and (
            not band or a.age_min_months <= band[1] and a.age_max_months >= band[0]) and (
            not p.kind or a.kind == p.kind) and (not p.interests or bool(set(p.interests) & set(a.interests))) and (
            not p.time or a.duration <= int(p.time)) and (not p.budget or a.cost <= int(p.budget)) and (
            not p.setting or a.setting == p.setting) and (not p.category or p.category in a.tags)
    return tuple(a for a in activities if matches(a))

@dataclass(frozen=True)
class Recommendation:
    activity_ids: tuple[str, ...]
    reason: str
    source: str = "deterministic catalog filter"

def recommend(activities, preferences):
    return Recommendation(tuple(a.id for a in filter_activities(activities, preferences)),
        "Based on your selected preferences." if preferences.submitted else "Choose a few preferences to tailor these ideas.")

class Catalog(Protocol):
    def activities(self) -> tuple[Activity, ...]: ...

def filter_chips(p, path="/", anchor="just-for-you"):
    chips = []
    choices = {"age": {k:v[2] for k,v in AGE_BANDS.items()}, "kind": KINDS, "time": TIMES, "budget": BUDGETS, "setting": SETTINGS, "category": CATEGORY_LABELS}
    for key in ("q", *choices):
        value = getattr(p, key)
        if value:
            label = f'“{value}”' if key == "q" else choices[key][value]
            chips.append((label, preference_url(replace(p, **{key: ""}), path, anchor)))
    for interest in p.interests:
        chips.append((INTERESTS[interest], preference_url(replace(p, interests=tuple(i for i in p.interests if i != interest)), path, anchor)))
    return chips
