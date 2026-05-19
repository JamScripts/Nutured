import html
import json
import os
from calendar import monthrange
from datetime import date, datetime, timezone
from urllib.parse import quote_plus, urlparse

from flask import Flask, jsonify, redirect, render_template_string, request
from openai import OpenAI

from milestones import format_milestones_for_prompt, get_relevant_cdc_milestones
from trusted_catalog import TRUSTED_PRODUCT_CATALOG


app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AMAZON_ID = os.environ.get("AMAZON_ID", "steppingstone-20")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

APPROVED_AMAZON_IMAGE_SOURCES = {"amazon_creators_api", "amazon_pa_api"}
AMAZON_IMAGE_HOSTS = {"m.media-amazon.com", "images-na.ssl-images-amazon.com"}
AMAZON_PRODUCT_HOSTS = {"amazon.com", "www.amazon.com", "smile.amazon.com"}
EVENT_LOG_PATH = "nurture_events.jsonl"
LEAD_LOG_PATH = "nurture_leads.jsonl"
PRIORITY_BRANDS = {
    "lovevery",
    "hape",
    "plantoys",
    "plan toys",
    "melissa & doug",
    "melissa and doug",
    "bannor toys",
    "tender leaf toys",
    "manhattan toy",
    "uncle goose",
}
CLEAN_MATERIAL_TERMS = {
    "wood",
    "wooden",
    "rubberwood",
    "hardwood",
    "basswood",
    "organic",
    "cotton",
    "silicone",
    "water-based",
    "non-toxic",
    "fsc",
}
OVERSTIMULATION_TERMS = {"battery", "batteries", "lights", "music", "electronic", "screen", "noisy"}
SEO_GUIDES = {
    "best-clean-toys-15-month-milestones": {
        "title": "Best Clean Toys for 15-Month Milestones",
        "description": "A milestone-first guide for parents choosing simple, safer toys around early walking, stacking, imitation, and self-feeding.",
        "bullets": [
            "Prioritize open-ended wooden stacking, posting, and feeding practice toys.",
            "Look for large pieces, water-based finishes, and simple play loops.",
            "Avoid noisy electronics when the goal is repetition, coordination, and imitation.",
        ],
    },
    "best-toys-for-spoon-practice": {
        "title": "Best Toys for Spoon Practice",
        "description": "Clean-swap feeding and pretend-play picks that support the CDC milestone of trying to use a spoon.",
        "bullets": [
            "Choose toddler-size spoons, bowls, and scoopable play activities.",
            "Connect the toy to mealtime practice instead of treating it as a separate skill.",
            "Watch for grip, wrist rotation, scooping, and repeated independent attempts.",
        ],
    },
    "montessori-toys-for-18-month-olds": {
        "title": "Montessori-Style Toys for 18-Month-Olds",
        "description": "Simple, low-stimulation toys that support early independence, movement, language, and practical-life play.",
        "bullets": [
            "Prefer real-world play: cups, bowls, brooms, puzzles, blocks, and baskets.",
            "Match toys to one visible skill so parents can observe progress.",
            "Keep the environment calm: fewer toys, clearer choices, more repetition.",
        ],
    },
    "non-toxic-gifts-for-2-year-olds": {
        "title": "Non-Toxic Gifts for 2-Year-Olds",
        "description": "A parent-friendly gift guide for toddlers moving into pretend play, language bursts, and multi-step play.",
        "bullets": [
            "Look for age-labeled toys with durable materials and transparent brand standards.",
            "Use pretend play, blocks, and puzzles to support language and problem solving.",
            "Avoid tiny pieces, brittle plastics, and overstimulating light-and-sound toys.",
        ],
    },
    "clean-swap-for-plastic-toddler-toys": {
        "title": "Clean Swap for Plastic Toddler Toys",
        "description": "How to decide whether to keep, skip, or replace a plastic toddler toy with a safer, more developmentally useful option.",
        "bullets": [
            "Skip toys with unclear materials, tiny detachable pieces, or loud passive entertainment.",
            "Keep durable items only when age fit, supervision, and developmental purpose are clear.",
            "Swap toward wood, organic cotton, food-grade silicone, and simple pretend-play tools.",
        ],
    },
}


NURTURE_WEEKLY_MILESTONES = {
    "Communication": [
        'Tries to say three or more words besides "mama" or "dada"',
        'Follows one-step directions without gestures, like "Give it to me"',
    ],
    "Motor": [
        "Walks without holding on to anyone or anything",
        "Scribbles",
        "Tries to use a spoon",
    ],
    "Social": [
        "Moves away from you, but looks to make sure you are close by",
        "Points to show you something interesting",
        "Looks at a few pages in a book with you",
    ],
    "Self-care": [
        "Drinks from a cup without a lid and may spill sometimes",
        "Feeds themself with fingers",
        "Helps you dress them by pushing an arm through a sleeve or lifting a foot",
    ],
}


def calculate_months(birth_date):
    today = date.today()
    return (today.year - birth_date.year) * 12 + today.month - birth_date.month


def default_birth_date_for_age(age_months=17):
    today = date.today()
    total_months = (today.year * 12 + today.month - 1) - age_months
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(today.day, monthrange(year, month)[1])
    return date(year, month, day)


def parse_birth_date(raw_birth_date):
    try:
        return date.fromisoformat(raw_birth_date)
    except (TypeError, ValueError):
        return default_birth_date_for_age()


def build_required_milestone_context(age_months):
    milestone_match = get_relevant_cdc_milestones(age_months)
    if not milestone_match:
        return ""

    _, milestones = milestone_match
    ordered_milestones = (
        milestones["social_emotional"]
        + milestones["language_communication"]
        + milestones["cognitive"]
        + milestones["movement_physical"]
    )
    required_phrases = ordered_milestones[:2]

    for milestone in ordered_milestones:
        if "spoon" in milestone.lower() and milestone not in required_phrases:
            required_phrases.append(milestone)

    return "\n".join(f"- {milestone}" for milestone in required_phrases)


def get_nurture_progress(seen_milestones):
    total_count = sum(len(milestones) for milestones in NURTURE_WEEKLY_MILESTONES.values())
    return len(seen_milestones), total_count


def extract_json_payload(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        last_fence = cleaned.rfind("```")
        if first_newline != -1 and last_fence > first_newline:
            cleaned = cleaned[first_newline:last_fence].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("OpenAI did not return a JSON object.")

    return json.loads(cleaned[start : end + 1])


def build_amazon_search_url(search_query):
    return f"https://www.amazon.com/s?k={quote_plus(search_query)}&tag={quote_plus(AMAZON_ID)}"


def append_jsonl(path, payload):
    event = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with open(path, "a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=True) + "\n")


def clean_text(raw_value):
    return str(raw_value or "").strip()


def get_profile_from_request():
    return {
        "child_name": clean_text(request.form.get("child_name")),
        "interests": clean_text(request.form.get("interests")),
        "budget": clean_text(request.form.get("budget")),
        "avoided_materials": clean_text(request.form.get("avoided_materials")),
        "gift_occasion": clean_text(request.form.get("gift_occasion")),
        "email": clean_text(request.form.get("email")),
        "subscribe_weekly": request.form.get("subscribe_weekly") == "on",
    }


def format_profile_for_prompt(profile):
    lines = []
    labels = {
        "child_name": "Child name",
        "interests": "Interests",
        "budget": "Budget",
        "avoided_materials": "Materials to avoid",
        "gift_occasion": "Gift occasion",
    }
    for key, label in labels.items():
        if profile.get(key):
            lines.append(f"- {label}: {profile[key]}")
    return "\n".join(lines) if lines else "- No saved parent profile yet."


def get_catalog_text(product):
    return " ".join(
        [
            product["brand"],
            product["title"],
            product["search_terms"],
            " ".join(product["materials"]),
            " ".join(product["milestones"]),
        ]
    ).lower()


def get_recommendation_text(recommendation):
    return " ".join(
        [
            recommendation.get("title", ""),
            recommendation.get("brand", ""),
            recommendation.get("cdc_milestone", ""),
            recommendation.get("why_it_matters", ""),
            recommendation.get("search_query", ""),
        ]
    ).lower()


def find_catalog_match(recommendation):
    recommendation_text = get_recommendation_text(recommendation)
    best_product = None
    best_score = 0

    for product in TRUSTED_PRODUCT_CATALOG:
        product_score = 0
        brand = product["brand"].lower()
        if brand in recommendation_text:
            product_score += 4
        for milestone in product["milestones"]:
            if milestone.lower() in recommendation_text:
                product_score += 3
        for term in product["search_terms"].lower().split():
            if len(term) > 3 and term in recommendation_text:
                product_score += 1

        if product_score > best_score:
            best_score = product_score
            best_product = product

    return best_product if best_score >= 3 else None


def get_verified_catalog_for_age(age_months, avoided_materials=""):
    avoided = avoided_materials.lower()
    eligible = []
    for product in TRUSTED_PRODUCT_CATALOG:
        product_text = get_catalog_text(product)
        if product["age_min"] <= age_months <= product["age_max"] and not any(
            material.strip() and material.strip().lower() in product_text
            for material in avoided.split(",")
        ):
            eligible.append(product)

    return eligible[:3] or TRUSTED_PRODUCT_CATALOG[:3]


def score_dimension(value, note):
    return {"score": int(value), "note": note}


def calculate_safety_score(recommendation, child_age):
    catalog_match = find_catalog_match(recommendation)
    recommendation_text = get_recommendation_text(recommendation)

    if catalog_match:
        age_fit = 100 if catalog_match["age_min"] <= child_age <= catalog_match["age_max"] else 65
        material_quality = 96
        brand_trust = 95
        small_parts = 86
        overstimulation = 94 if catalog_match["overstimulation_risk"].lower() == "low" else 70
        product_trust = "Verified catalog match"
        trust_note = catalog_match["small_parts_note"]
    else:
        age_fit = 76
        material_quality = 90 if any(term in recommendation_text for term in CLEAN_MATERIAL_TERMS) else 66
        brand_trust = 88 if any(brand in recommendation_text for brand in PRIORITY_BRANDS) else 62
        small_parts = 72
        overstimulation = 45 if any(term in recommendation_text for term in OVERSTIMULATION_TERMS) else 82
        product_trust = "AI-suggested, needs product verification"
        trust_note = "Confirm the final product age label, piece size, materials, and seller before buying."

    developmental_match = 92 if recommendation.get("cdc_milestone") else 70
    dimensions = {
        "Age fit": score_dimension(age_fit, "Matches the child age range." if age_fit >= 85 else "Check the final product age label."),
        "Material quality": score_dimension(material_quality, "Clean material signal is strong." if material_quality >= 85 else "Material details need verification."),
        "Small-parts concern": score_dimension(small_parts, trust_note),
        "Brand trust": score_dimension(brand_trust, product_trust),
        "Developmental match": score_dimension(developmental_match, recommendation.get("cdc_milestone", "Developmental link needs review.")),
        "Overstimulation risk": score_dimension(overstimulation, "Low-sensory, open-ended play." if overstimulation >= 85 else "Avoid loud, flashy, or screen-heavy variants."),
    }
    overall = round(sum(item["score"] for item in dimensions.values()) / len(dimensions))

    return {
        "overall": overall,
        "label": "High trust" if overall >= 86 else "Review before buying" if overall >= 70 else "Use caution",
        "catalog_match": catalog_match,
        "dimensions": dimensions,
    }


def is_approved_amazon_image_url(image_url):
    parsed = urlparse(image_url)
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() in AMAZON_IMAGE_HOSTS
        and parsed.path.startswith("/images/")
    )


def is_amazon_product_url(product_url):
    parsed = urlparse(product_url)
    return parsed.scheme == "https" and parsed.netloc.lower() in AMAZON_PRODUCT_HOSTS


def infer_material_label(recommendation):
    text = " ".join(
        [
            recommendation.get("title", ""),
            recommendation.get("brand", ""),
            recommendation.get("why_it_matters", ""),
            recommendation.get("search_query", ""),
        ]
    ).lower()

    if "organic" in text or "cotton" in text:
        return "Organic"
    if "silicone" in text:
        return "Silicone"
    if "wood" in text or "wooden" in text or "hape" in text or "plantoys" in text:
        return "Wood"
    return "Clean"


def render_product_visual(recommendation, amazon_url):
    image_url = recommendation.get("image_url", "")
    product_url = recommendation.get("amazon_product_url", "")
    image_alt = html.escape(recommendation.get("image_alt") or recommendation["title"])

    if image_url and product_url:
        escaped_image_url = html.escape(image_url, quote=True)
        escaped_product_url = html.escape(build_tracking_url(recommendation["title"], product_url), quote=True)
        return f"""
        <a class="product-visual product-image-link" href="{escaped_product_url}" target="_blank" rel="noopener noreferrer">
            <img class="product-image" src="{escaped_image_url}" alt="{image_alt}" loading="lazy">
        </a>
        """

    material_label = html.escape(infer_material_label(recommendation))
    escaped_amazon_url = html.escape(amazon_url, quote=True)
    return f"""
    <a class="product-visual product-image-placeholder" href="{escaped_amazon_url}" target="_blank" rel="noopener noreferrer">
        <span class="material-orb">{material_label[:1]}</span>
        <strong>{material_label} pick</strong>
        <small>Official Amazon image preview pending</small>
    </a>
    """


def normalize_recommendation(recommendation, child_age=None):
    title = recommendation.get("title") or recommendation.get("name") or "Developmental Gift"
    brand = recommendation.get("brand") or "Clean-swap pick"
    milestone = recommendation.get("cdc_milestone") or recommendation.get("milestone_logic") or "CDC milestone"
    why_it_matters = recommendation.get("why_it_matters") or recommendation.get("description") or ""
    confidence_label = recommendation.get("confidence_label") or recommendation.get("confidence") or "Good next step"
    timeline = recommendation.get("timeline") if isinstance(recommendation.get("timeline"), dict) else {}
    current_milestone = timeline.get("current_milestone") or recommendation.get("current_milestone") or milestone
    skill_strengthened = (
        timeline.get("skill_strengthened")
        or recommendation.get("skill_strengthened")
        or "Targeted developmental practice"
    )
    recommended_toy = timeline.get("recommended_toy") or recommendation.get("recommended_toy") or title
    what_to_observe = (
        timeline.get("what_to_observe")
        or recommendation.get("what_to_observe")
        or recommendation.get("what_to_watch")
        or "Watch for curiosity, repetition, and small gains in independence."
    )
    image_source = str(recommendation.get("image_source") or "").strip()
    image_url = str(recommendation.get("image_url") or "").strip()
    amazon_product_url = str(recommendation.get("amazon_product_url") or recommendation.get("product_url") or "").strip()
    search_query = (
        recommendation.get("search_query")
        or recommendation.get("amazon_search_term")
        or title
    )

    if (
        image_source not in APPROVED_AMAZON_IMAGE_SOURCES
        or not is_approved_amazon_image_url(image_url)
        or not is_amazon_product_url(amazon_product_url)
    ):
        image_source = ""
        image_url = ""
        amazon_product_url = ""

    normalized = {
        "title": str(title),
        "brand": str(brand),
        "cdc_milestone": str(milestone),
        "confidence_label": str(confidence_label),
        "timeline": {
            "current_milestone": str(current_milestone),
            "skill_strengthened": str(skill_strengthened),
            "recommended_toy": str(recommended_toy),
            "what_to_observe": str(what_to_observe),
        },
        "why_it_matters": str(why_it_matters),
        "search_query": str(search_query),
        "image_alt": str(recommendation.get("image_alt") or title),
        "image_source": image_source,
        "image_url": image_url,
        "amazon_product_url": amazon_product_url,
    }
    normalized["safety_score"] = calculate_safety_score(normalized, child_age or 18)
    return normalized


def normalize_mission(mission):
    return {
        "title": str(mission.get("title") or mission.get("mission") or "This week's mission: Practice a new skill"),
        "activity": str(mission.get("activity") or "Build one short play routine around this skill."),
        "toy_connection": str(
            mission.get("toy_connection")
            or mission.get("toy_angle")
            or "Use a simple, clean-material toy that invites repetition."
        ),
        "what_to_watch": str(
            mission.get("what_to_watch")
            or mission.get("watch_for")
            or "Watch for attempts, imitation, and confidence."
        ),
    }


def normalize_agent_payload(payload):
    if not isinstance(payload, dict):
        payload = {}

    clean_swap_review = payload.get("clean_swap_review") or payload.get("clean_swap")
    if not isinstance(clean_swap_review, dict):
        clean_swap_review = {}

    missions = payload.get("missions") or payload.get("mission_cards") or []
    if not isinstance(missions, list):
        missions = []

    recommendations = payload.get("recommendations") or []
    if not isinstance(recommendations, list):
        recommendations = []

    return {
        "scout_summary": str(payload.get("scout_summary") or payload.get("scout_mode") or payload.get("summary") or ""),
        "weekly_brief": str(payload.get("weekly_brief") or ""),
        "clean_swap_review": {
            "verdict": str(clean_swap_review.get("verdict") or ""),
            "reason": str(clean_swap_review.get("reason") or clean_swap_review.get("why") or ""),
            "swap_strategy": str(clean_swap_review.get("swap_strategy") or clean_swap_review.get("swap") or ""),
        },
        "missions": [normalize_mission(mission) for mission in missions[:3] if isinstance(mission, dict)],
        "recommendations": recommendations[:3],
    }


def render_agent_overview(insights):
    scout_summary = insights.get("scout_summary", "").strip()
    weekly_brief = insights.get("weekly_brief", "").strip()
    clean_swap_review = insights.get("clean_swap_review", {})
    clean_swap_content = "".join(clean_swap_review.values()).strip()
    cards = []

    if scout_summary:
        cards.append(
            f"""
            <article class="agent-card scout-card">
                <span class="agent-label">Nurture Scout Mode</span>
                <p>{html.escape(scout_summary)}</p>
            </article>
            """
        )

    if weekly_brief:
        cards.append(
            f"""
            <article class="agent-card weekly-card">
                <span class="agent-label">Weekly Nurture Brief</span>
                <p>{html.escape(weekly_brief)}</p>
            </article>
            """
        )

    if clean_swap_content:
        cards.append(
            f"""
            <article class="agent-card clean-swap-card">
                <span class="agent-label">Clean Swap Agent</span>
                <h3>{html.escape(clean_swap_review.get("verdict", "Clean swap review"))}</h3>
                <p>{html.escape(clean_swap_review.get("reason", ""))}</p>
                <p><strong>Cleaner path:</strong> {html.escape(clean_swap_review.get("swap_strategy", ""))}</p>
            </article>
            """
        )

    if not cards:
        return ""

    return f'<section class="agent-overview">{"".join(cards)}</section>'


def render_scout_response(insights):
    scout_summary = insights.get("scout_summary", "").strip()
    if not scout_summary:
        return ""

    return f"""
    <section class="scout-response">
        <span class="agent-label">Nurture Scout Mode</span>
        <h2>Nurture's read</h2>
        <p>{html.escape(scout_summary)}</p>
    </section>
    """


def render_clean_swap_panel(insights):
    clean_swap_review = insights.get("clean_swap_review", {})
    clean_swap_content = "".join(clean_swap_review.values()).strip()
    if not clean_swap_content:
        return """
        <section class="tab-panel-card">
            <span class="agent-label">Clean Swap Agent</span>
            <h3>No specific toy pasted yet</h3>
            <p>Paste a toy name or Amazon link into the search box and Nurture will decide whether to keep it, skip it, or swap it for a cleaner developmental match.</p>
        </section>
        """

    return f"""
    <section class="tab-panel-card">
        <span class="agent-label">Clean Swap Agent</span>
        <h3>{html.escape(clean_swap_review.get("verdict", "Clean swap review"))}</h3>
        <p>{html.escape(clean_swap_review.get("reason", ""))}</p>
        <p><strong>Better clean swap:</strong> {html.escape(clean_swap_review.get("swap_strategy", ""))}</p>
    </section>
    """


def render_weekly_brief_panel(insights):
    weekly_brief = insights.get("weekly_brief", "").strip()
    if not weekly_brief:
        return ""

    return f"""
    <section class="tab-panel-card">
        <span class="agent-label">Weekly Nurture Brief</span>
        <h3>This week's focus</h3>
        <p>{html.escape(weekly_brief)}</p>
        <ul class="brief-list">
            <li>3 activities matched to the current milestone window</li>
            <li>3 clean toy suggestions with safety reasoning</li>
            <li>1 safety tip and 1 milestone to watch</li>
        </ul>
    </section>
    """


def render_mission_cards(missions):
    if not missions:
        return ""

    cards = []
    for mission in missions:
        cards.append(
            f"""
            <article class="mission-card">
                <span class="agent-label">Milestone Mission</span>
                <h3>{html.escape(mission["title"])}</h3>
                <p><strong>Activity:</strong> {html.escape(mission["activity"])}</p>
                <p><strong>Toy angle:</strong> {html.escape(mission["toy_connection"])}</p>
                <p><strong>Watch for:</strong> {html.escape(mission["what_to_watch"])}</p>
            </article>
            """
        )

    return f"""
    <section class="mission-section">
        <h2>Milestone-to-Mission Cards</h2>
        <div class="mission-grid">
            {''.join(cards)}
        </div>
    </section>
    """


def render_safety_score(score_data):
    dimensions = []
    for name, detail in score_data["dimensions"].items():
        dimensions.append(
            f"""
            <li>
                <span>{html.escape(name)}</span>
                <strong>{detail["score"]}</strong>
                <small>{html.escape(detail["note"])}</small>
            </li>
            """
        )

    return f"""
    <div class="safety-score-card">
        <div class="score-header">
            <span>Nurture Safety Score</span>
            <strong>{score_data["overall"]}</strong>
        </div>
        <p>{html.escape(score_data["label"])}: scored across age fit, materials, choking concern, brand trust, developmental match, and overstimulation risk.</p>
        <ul>
            {''.join(dimensions)}
        </ul>
    </div>
    """


def render_catalog_match_badge(score_data):
    catalog_match = score_data.get("catalog_match")
    if catalog_match:
        return f"""
        <div class="trust-badge verified">
            Verified pick database match: {html.escape(catalog_match["brand"])}
        </div>
        """

    return """
    <div class="trust-badge review">
        Product trust layer: verify exact item before purchase
    </div>
    """


def build_tracking_url(title, amazon_url):
    return f"/go?title={quote_plus(title)}&url={quote_plus(amazon_url)}"


def render_recommendations_grid(recommendations, child_age):
    normalized_recommendations = [normalize_recommendation(item, child_age) for item in recommendations[:3]]
    cards = []

    for index, recommendation in enumerate(normalized_recommendations):
        title = html.escape(recommendation["title"])
        brand = html.escape(recommendation["brand"])
        milestone = html.escape(recommendation["cdc_milestone"])
        confidence_label = html.escape(recommendation["confidence_label"])
        timeline = recommendation["timeline"]
        why_it_matters = html.escape(recommendation["why_it_matters"])
        raw_amazon_url = build_amazon_search_url(recommendation["search_query"])
        raw_tracked_amazon_url = build_tracking_url(recommendation["title"], raw_amazon_url)
        tracked_amazon_url = html.escape(raw_tracked_amazon_url, quote=True)
        product_visual = render_product_visual(recommendation, raw_tracked_amazon_url)
        safety_score = render_safety_score(recommendation["safety_score"])
        catalog_badge = render_catalog_match_badge(recommendation["safety_score"])
        badge = '<span class="top-pick-badge">TOP PICK</span>' if index == 0 else ""

        cards.append(
            f"""
            <article class="product-recommendation-card">
                {badge}
                {product_visual}
                <div class="card-brand">{brand}</div>
                <h3>{title}</h3>
                <span class="confidence-label">{confidence_label}</span>
                {catalog_badge}
                <div class="why-it-matters">
                    <strong>Why it Matters</strong>
                    <p>{why_it_matters}</p>
                    <p><strong>CDC milestone:</strong> {milestone}</p>
                </div>
                <details class="card-details">
                    <summary>Safety score and reasoning</summary>
                    {safety_score}
                    <div class="development-chain">
                        <strong>Developmental reasoning</strong>
                        <div class="chain-step"><span>Current milestone</span><p>{html.escape(timeline["current_milestone"])}</p></div>
                        <div class="chain-arrow">&rarr;</div>
                        <div class="chain-step"><span>Skill strengthened</span><p>{html.escape(timeline["skill_strengthened"])}</p></div>
                        <div class="chain-arrow">&rarr;</div>
                        <div class="chain-step"><span>Recommended toy</span><p>{html.escape(timeline["recommended_toy"])}</p></div>
                        <div class="chain-arrow">&rarr;</div>
                        <div class="chain-step"><span>What to observe</span><p>{html.escape(timeline["what_to_observe"])}</p></div>
                    </div>
                </details>
                <div class="marketplace-button-row">
                    <a class="marketplace-button" href="{tracked_amazon_url}" target="_blank" rel="noopener noreferrer" data-track-action="amazon_click" data-track-title="{title}">
                        View on Amazon
                    </a>
                </div>
                <div class="feedback-row">
                    <button type="button" class="feedback-button" data-track-action="save" data-track-title="{title}">Save</button>
                    <button type="button" class="feedback-button" data-track-action="reject" data-track-title="{title}">Not for us</button>
                </div>
            </article>
            """
        )

    while len(cards) < 3:
        cards.append(
            """
            <article class="product-recommendation-card placeholder-card">
                <div class="product-visual product-image-placeholder">
                    <span class="material-orb">N</span>
                    <strong>More clean picks</strong>
                    <small>Waiting for a full agent result</small>
                </div>
                <h3>Additional recommendation pending</h3>
                <p>Nurture will fill this space when the agent returns another safe, milestone-matched toy.</p>
            </article>
            """
        )

    return "\n".join(cards)


def render_verified_catalog(age_months, avoided_materials):
    products = get_verified_catalog_for_age(age_months, avoided_materials)
    cards = []
    for product in products:
        amazon_url = build_amazon_search_url(product["search_terms"])
        tracked_url = html.escape(build_tracking_url(product["title"], amazon_url), quote=True)
        product_title = html.escape(product["title"])
        product_title_attr = html.escape(product["title"], quote=True)
        product_brand = html.escape(product["brand"])
        materials = ", ".join(product["materials"])
        milestones = "; ".join(product["milestones"][:2])
        cards.append(
            f"""
            <article class="verified-product-card">
                <span class="agent-label">Verified Product Database</span>
                <h3>{product_brand}: {product_title}</h3>
                <p><strong>Age fit:</strong> {product["age_min"]}-{product["age_max"]} months</p>
                <p><strong>Materials:</strong> {html.escape(materials)}</p>
                <p><strong>Milestone fit:</strong> {html.escape(milestones)}</p>
                <p><strong>Safety note:</strong> {html.escape(product["small_parts_note"])}</p>
                <a class="marketplace-button compact-button" href="{tracked_url}" target="_blank" rel="noopener noreferrer" data-track-action="catalog_click" data-track-title="{product_title_attr}">View clean pick</a>
            </article>
            """
        )

    return f"""
    <section>
        <h2>Verified Clean Picks</h2>
        <p class="muted">A manually curated product trust layer we can improve before full Amazon image/API access unlocks.</p>
        <div class="verified-grid">
            {''.join(cards)}
        </div>
    </section>
    """


def render_affiliate_disclosure():
    return """
    <section class="trust-disclosure">
        <strong>Affiliate Disclosure</strong>
        <span>Nurture may earn from qualifying purchases. Recommendations are selected for developmental fit, material quality, and product trust signals before commerce links.</span>
    </section>
    """


def render_advisor_profile(profile, subscription_notice):
    checked = "checked" if profile.get("subscribe_weekly") else ""
    return f"""
    <section>
        <h2>Parent Advisor Profile</h2>
        <p class="muted">Saved in this browser so Nurture can remember age, preferences, budget, and materials to avoid.</p>
        <div class="profile-memory-grid">
            <label>
                Child name
                <input type="text" name="child_name" data-memory-key="child_name" value="{html.escape(profile.get("child_name", ""), quote=True)}" placeholder="Ava">
            </label>
            <label>
                Interests
                <input type="text" name="interests" data-memory-key="interests" value="{html.escape(profile.get("interests", ""), quote=True)}" placeholder="water play, pretend food, books">
            </label>
            <label>
                Budget
                <input type="text" name="budget" data-memory-key="budget" value="{html.escape(profile.get("budget", ""), quote=True)}" placeholder="$25-$60">
            </label>
            <label>
                Materials to avoid
                <input type="text" name="avoided_materials" data-memory-key="avoided_materials" value="{html.escape(profile.get("avoided_materials", ""), quote=True)}" placeholder="PVC, BPA, loud electronics">
            </label>
            <label>
                Gift occasion
                <input type="text" name="gift_occasion" data-memory-key="gift_occasion" value="{html.escape(profile.get("gift_occasion", ""), quote=True)}" placeholder="birthday, weekly practice, grandparent gift">
            </label>
            <label>
                Weekly brief email
                <input type="email" name="email" data-memory-key="email" value="{html.escape(profile.get("email", ""), quote=True)}" placeholder="parent@example.com">
            </label>
        </div>
        <label class="subscribe-check">
            <input type="checkbox" name="subscribe_weekly" data-memory-key="subscribe_weekly" {checked}>
            <span>Send a weekly Nurture brief with 3 activities, 3 clean picks, 1 safety tip, and 1 milestone to watch.</span>
        </label>
        {subscription_notice}
    </section>
    """


def render_growth_tracker(months, checked_count, total_count, progress_percent, milestone_checkboxes):
    return f"""
    <section class="growth-tracker">
        <h2>Child Profile & Developmental Progress</h2>
        <div class="profile-grid">
            <div class="age-metric">
                <span>Age in months</span>
                <strong>{months}m</strong>
            </div>
            <div class="profile-panel">
                <div class="milestone-grid">
                    {milestone_checkboxes}
                </div>
            </div>
        </div>
        <div class="progress-track">
            <div class="progress-fill" style="width: {progress_percent}%;"></div>
        </div>
        <p class="muted">{checked_count} of {total_count} milestones seen today</p>
    </section>
    """


def render_seo_links():
    links = []
    for slug, guide in SEO_GUIDES.items():
        links.append(f'<a href="/guides/{html.escape(slug, quote=True)}">{html.escape(guide["title"])}</a>')
    return f"""
    <section class="seo-link-section">
        <p class="muted">Indexable guide pages for clean toys, milestones, and safer toddler gift decisions.</p>
        <div class="seo-link-grid">
            {''.join(links)}
        </div>
    </section>
    """


def render_guide_panel(slug):
    guide = SEO_GUIDES.get(slug)
    if not guide:
        return ""

    return f"""
    <section class="guide-panel">
        <span class="agent-label">Nurture Guide</span>
        <h2>{html.escape(guide["title"])}</h2>
        <p>{html.escape(guide["description"])}</p>
        <ul>
            {''.join(f"<li>{html.escape(item)}</li>" for item in guide["bullets"])}
        </ul>
    </section>
    """


def get_nurture_agent_response(user_input, child_age, seen_milestones, profile):
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your Railway environment variables.")

    milestone_context = format_milestones_for_prompt(child_age)
    required_milestones = build_required_milestone_context(child_age)
    seen_milestone_context = (
        "\n".join(f"- {milestone}" for milestone in sorted(seen_milestones))
        if seen_milestones
        else "- No milestones checked today."
    )
    profile_context = format_profile_for_prompt(profile)
    system_prompt = f"""
    You are Nurture, an expert child development scout and clean-swap toy agent.
    The child is {child_age} months old.

    Use this CDC milestone context as the source of truth:
    {milestone_context}

    Required CDC milestone phrases to consider:
    {required_milestones}

    Milestones the parent checked today:
    {seen_milestone_context}

    Parent advisor profile:
    {profile_context}

    Agent behavior:
    - Start with Nurture Scout Mode: infer the developmental pattern behind the user's request.
    - Use the parent advisor profile to respect interests, budget, avoided materials, and gift occasion.
    - Create practical Milestone-to-Mission cards parents can try this week.
    - If the user pasted or named a specific toy/product, include a Clean Swap Agent verdict. If not, set clean_swap_review values to empty strings.
    - Give every recommendation a confidence_label: "Strong match", "Good next step", or "Stretch milestone".
    - Include a developmental reasoning timeline for each recommendation.
    - Do not invent, scrape, or guess Amazon product image URLs. Leave image_url, image_source, and amazon_product_url empty unless they were supplied by an official Amazon Creators API or PA API result.
    - Never recommend plastic junk, noisy gimmicks, or unverified safety brands.
    - Prioritize Lovevery, Hape, PlanToys, Melissa & Doug, wooden toys, organic cotton, food-grade silicone, and water-based finishes.

    Suggest exactly 3 clean-swap toys: non-toxic, wooden, organic, or food-grade silicone.
    Return a valid JSON object with this exact shape:
    {{
      "scout_summary": "I am seeing a self-feeding pattern here. For 15 months, focus on spoon use, cup practice, and fine motor control.",
      "weekly_brief": "This week, focus on self-feeding, early pretend play, and one-step directions.",
      "clean_swap_review": {{
        "verdict": "Skip it" or "Good clean-swap fit" or "",
        "reason": "One sentence about material/development fit, or empty string.",
        "swap_strategy": "One sentence describing the cleaner replacement path, or empty string."
      }},
      "missions": [
        {{
          "title": "This week's mission: Practice scooping",
          "activity": "A parent-friendly activity.",
          "toy_connection": "How a clean-material toy supports the mission.",
          "what_to_watch": "What parents should observe."
        }}
      ],
      "recommendations": [
        {{
          "name": "Product search title",
          "brand": "Brand or material category",
          "description": "Short product description",
          "milestone_logic": "Explicitly name a CDC milestone from the context and explain why this toy supports it.",
          "confidence_label": "Strong match",
          "amazon_search_term": "Amazon search query",
          "image_url": "",
          "image_source": "",
          "amazon_product_url": "",
          "image_alt": "Accessible product image description",
          "timeline": {{
            "current_milestone": "Exact CDC milestone phrase from the context",
            "skill_strengthened": "Plain-English skill this toy strengthens",
            "recommended_toy": "Recommended toy name",
            "what_to_observe": "What parents should look for during play"
          }}
        }}
      ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        response_format={"type": "json_object"},
    )
    payload = extract_json_payload(response.choices[0].message.content or "")
    return normalize_agent_payload(payload)


def render_milestone_checkboxes(seen_milestones):
    sections = []
    for category, milestones in NURTURE_WEEKLY_MILESTONES.items():
        items = []
        for milestone in milestones:
            checked = "checked" if milestone in seen_milestones else ""
            escaped_milestone = html.escape(milestone)
            items.append(
                f"""
                <label class="milestone-check">
                    <input type="checkbox" name="seen_milestones" value="{escaped_milestone}" {checked}>
                    <span>{escaped_milestone}</span>
                </label>
                """
            )
        sections.append(
            f"""
            <section class="milestone-group">
                <h3>{html.escape(category)}</h3>
                {''.join(items)}
            </section>
            """
        )
    return "\n".join(sections)


PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ seo_title }}</title>
    <meta name="description" content="{{ seo_description }}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Quicksand:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --sky-blue: #87CEEB;
            --rose-pink: #F497AD;
            --charcoal: #2C3E50;
            --background: #F8F9FA;
            --line: #E0E0E0;
            --white: #FFFFFF;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: var(--background);
            color: var(--charcoal);
            font-family: 'Inter', sans-serif;
        }

        main {
            width: min(1180px, calc(100% - 32px));
            margin: 0 auto;
            padding: 40px 0 28px;
        }

        h1,
        h2,
        h3 {
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            letter-spacing: 0;
        }

        .hero-header {
            margin: 0 auto 32px;
            text-align: center;
        }

        .logo-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: var(--white);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            font-size: 28px;
        }

        .nurture-title {
            margin: 8px 0 4px;
            font-size: clamp(44px, 6vw, 64px);
            line-height: 1;
        }

        .section-kicker,
        .muted {
            color: var(--charcoal);
        }

        .search-panel,
        .profile-panel,
        .agent-card,
        .mission-card,
        .safety-guide-bar {
            background: var(--white);
            border: 1px solid var(--line);
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            padding: 20px;
        }

        .search-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 180px auto;
            gap: 12px;
            align-items: end;
        }

        label {
            display: grid;
            gap: 6px;
            color: var(--charcoal);
            font-weight: 700;
        }

        input[type="text"],
        input[type="email"],
        input[type="date"] {
            width: 100%;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 13px 16px;
            color: var(--charcoal);
            background: var(--white);
            font: inherit;
        }

        button,
        .marketplace-button {
            border: 0;
            border-radius: 999px;
            padding: 13px 22px;
            background: var(--rose-pink);
            color: #FFFFFF;
            cursor: pointer;
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
            text-decoration: none;
            box-shadow: 0 10px 24px rgba(244, 151, 173, 0.26);
        }

        .intake-shell,
        .results-workspace,
        .setup-drawer,
        .feature-drawer {
            margin-bottom: 22px;
        }

        .intake-shell {
            max-width: 980px;
            margin-inline: auto;
        }

        .setup-drawer,
        .feature-drawer {
            border: 1px solid var(--line);
            border-radius: 20px;
            background: var(--white);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            overflow: hidden;
        }

        .setup-drawer summary,
        .feature-drawer summary {
            cursor: pointer;
            padding: 16px 20px;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
        }

        .setup-drawer > section,
        .setup-drawer .growth-tracker,
        .feature-drawer > *:not(summary) {
            padding: 0 20px 20px;
        }

        .empty-state {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 16px;
            margin: 24px 0;
        }

        .empty-state-card,
        .scout-response,
        .tab-panel-card {
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 20px;
            background: var(--white);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        }

        .scout-response {
            margin: 18px 0;
        }

        .scout-response h2 {
            margin: 12px 0 8px;
        }

        .result-tabs {
            position: relative;
            margin-top: 18px;
        }

        .result-tabs > input[type="radio"] {
            position: absolute;
            opacity: 0;
            pointer-events: none;
        }

        .tab-labels {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 16px;
        }

        .tab-labels label {
            display: inline-flex;
            cursor: pointer;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 10px 14px;
            background: var(--white);
            color: var(--charcoal);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
        }

        .tab-panel {
            display: none;
        }

        #tab-recommendations:checked ~ .tab-labels label[for="tab-recommendations"],
        #tab-missions:checked ~ .tab-labels label[for="tab-missions"],
        #tab-safety:checked ~ .tab-labels label[for="tab-safety"],
        #tab-clean-swap:checked ~ .tab-labels label[for="tab-clean-swap"],
        #tab-profile:checked ~ .tab-labels label[for="tab-profile"],
        #tab-verified:checked ~ .tab-labels label[for="tab-verified"],
        #tab-weekly:checked ~ .tab-labels label[for="tab-weekly"],
        #tab-guides:checked ~ .tab-labels label[for="tab-guides"] {
            border-color: var(--rose-pink);
            background: var(--rose-pink);
            color: #FFFFFF;
        }

        #tab-recommendations:checked ~ .tab-panels .recommendations-panel,
        #tab-missions:checked ~ .tab-panels .missions-panel,
        #tab-safety:checked ~ .tab-panels .safety-panel,
        #tab-clean-swap:checked ~ .tab-panels .clean-swap-panel,
        #tab-profile:checked ~ .tab-panels .profile-panel-tab,
        #tab-verified:checked ~ .tab-panels .verified-panel,
        #tab-weekly:checked ~ .tab-panels .weekly-panel,
        #tab-guides:checked ~ .tab-panels .guides-panel {
            display: block;
        }

        .trust-disclosure,
        .guide-panel,
        .seo-link-section {
            margin: 0 0 28px;
            padding: 18px 20px;
            border: 1px solid var(--line);
            border-radius: 20px;
            background: var(--white);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        }

        .trust-disclosure {
            display: flex;
            gap: 14px;
            align-items: center;
        }

        .trust-disclosure strong {
            flex: 0 0 auto;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
        }

        .profile-memory-grid,
        .verified-grid,
        .seo-link-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 16px;
            margin: 18px 0;
        }

        .subscribe-check {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            max-width: 56rem;
            margin-top: 10px;
            font-weight: 600;
        }

        .subscription-notice {
            margin-top: 12px;
            border-radius: 14px;
            padding: 12px 14px;
            background: rgba(135, 206, 235, 0.18);
            color: var(--charcoal);
            font-weight: 700;
        }

        .verified-product-card {
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 18px;
            background: var(--white);
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        }

        .verified-product-card h3 {
            margin: 14px 0 10px;
            font-size: 20px;
        }

        .compact-button {
            display: inline-flex;
            margin-top: 10px;
            padding: 10px 16px;
        }

        .seo-link-grid a {
            display: block;
            border: 1px solid rgba(135, 206, 235, 0.38);
            border-radius: 14px;
            padding: 14px 16px;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
            text-decoration: none;
            background: #F8F9FA;
        }

        .agent-overview,
        .mission-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 20px;
            margin: 18px 0 34px;
        }

        .agent-card,
        .mission-card {
            min-height: 12rem;
        }

        .agent-label,
        .confidence-label {
            display: inline-flex;
            width: fit-content;
            align-items: center;
            border-radius: 999px;
            padding: 5px 10px;
            background: rgba(244, 151, 173, 0.14);
            color: var(--rose-pink);
            font-family: 'Quicksand', sans-serif;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .agent-card h3,
        .mission-card h3 {
            margin: 14px 0 10px;
            font-size: 21px;
        }

        .mission-section {
            margin-top: 28px;
        }

        .recommendation-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 20px;
            margin: 18px 0 34px;
        }

        .product-recommendation-card {
            position: relative;
            min-height: 25rem;
            padding: 20px;
            background-color: #FFFFFF;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            border: 1px solid #E0E0E0;
            transition: transform 180ms ease, box-shadow 180ms ease;
        }

        .product-recommendation-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 14px 30px rgba(0,0,0,0.1);
        }

        .product-visual {
            display: grid;
            place-items: center;
            width: 100%;
            min-height: 180px;
            margin-bottom: 18px;
            overflow: hidden;
            border: 1px solid rgba(135, 206, 235, 0.38);
            border-radius: 16px;
            background: #F8F9FA;
            color: var(--charcoal);
            text-align: center;
            text-decoration: none;
        }

        .product-image {
            width: 100%;
            height: 210px;
            object-fit: contain;
            padding: 16px;
            background: #FFFFFF;
        }

        .product-image-placeholder {
            gap: 8px;
            padding: 20px;
            background:
                linear-gradient(135deg, rgba(135, 206, 235, 0.18), rgba(244, 151, 173, 0.18)),
                #F8F9FA;
        }

        .product-image-placeholder strong {
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-size: 22px;
        }

        .product-image-placeholder small {
            max-width: 14rem;
            color: #64747a;
            font-weight: 700;
        }

        .material-orb {
            display: grid;
            place-items: center;
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: var(--white);
            color: var(--rose-pink);
            font-family: 'Quicksand', sans-serif;
            font-size: 26px;
            font-weight: 700;
            box-shadow: 0 10px 24px rgba(0,0,0,0.08);
        }

        .product-recommendation-card h3 {
            margin: 12px 0 10px;
            font-size: 22px;
            line-height: 1.2;
        }

        .top-pick-badge {
            position: absolute;
            top: 14px;
            right: 14px;
            display: inline-block;
            border-radius: 4px;
            padding: 5px 10px;
            background: var(--rose-pink);
            color: #FFFFFF;
            font-family: 'Quicksand', sans-serif;
            font-size: 12px;
            font-weight: 700;
        }

        .card-brand {
            color: #64747a;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .why-it-matters {
            margin-top: 18px;
            padding-top: 14px;
            border-top: 1px solid rgba(135, 206, 235, 0.38);
        }

        .trust-badge {
            margin-top: 12px;
            border-radius: 12px;
            padding: 10px 12px;
            font-weight: 700;
        }

        .trust-badge.verified {
            background: rgba(135, 206, 235, 0.18);
            color: #246174;
        }

        .trust-badge.review {
            background: rgba(244, 151, 173, 0.14);
            color: #94435a;
        }

        .safety-score-card {
            margin-top: 18px;
            border: 1px solid rgba(135, 206, 235, 0.38);
            border-radius: 14px;
            padding: 14px;
            background: #F8F9FA;
        }

        .score-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
        }

        .score-header strong {
            display: grid;
            place-items: center;
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: var(--white);
            color: var(--rose-pink);
            font-size: 22px;
            box-shadow: 0 10px 24px rgba(0,0,0,0.08);
        }

        .safety-score-card ul {
            display: grid;
            gap: 8px;
            margin: 12px 0 0;
            padding: 0;
            list-style: none;
        }

        .safety-score-card li {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 6px 10px;
            border-top: 1px solid rgba(44, 62, 80, 0.09);
            padding-top: 8px;
        }

        .safety-score-card li small {
            grid-column: 1 / -1;
            color: #64747a;
        }

        .development-chain {
            display: grid;
            gap: 8px;
            margin-top: 18px;
            padding: 14px;
            border: 1px solid rgba(135, 206, 235, 0.38);
            border-radius: 14px;
            background: #F8F9FA;
        }

        .chain-step span {
            display: block;
            color: #64747a;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .chain-step p {
            margin: 4px 0 0;
        }

        .chain-arrow {
            color: var(--rose-pink);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
        }

        .card-details {
            margin-top: 16px;
            border: 1px solid rgba(135, 206, 235, 0.38);
            border-radius: 14px;
            background: #F8F9FA;
            overflow: hidden;
        }

        .card-details summary {
            cursor: pointer;
            padding: 12px 14px;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-weight: 700;
        }

        .card-details .safety-score-card,
        .card-details .development-chain {
            margin: 0 12px 12px;
        }

        .marketplace-button-row {
            margin-top: 18px;
            text-align: center;
        }

        .feedback-row {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 12px;
        }

        .feedback-button {
            border: 1px solid var(--line);
            box-shadow: none;
            background: var(--white);
            color: var(--charcoal);
            padding: 9px 14px;
        }

        .report-actions {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: -16px 0 34px;
        }

        .secondary-action {
            border: 1px solid var(--line);
            box-shadow: none;
            background: var(--white);
            color: var(--charcoal);
        }

        #copy-report-status {
            color: #64747a;
            font-weight: 700;
        }

        .profile-grid {
            display: grid;
            grid-template-columns: 220px 1fr;
            gap: 20px;
            margin: 18px 0 34px;
        }

        .age-metric {
            display: grid;
            place-items: center;
            min-height: 118px;
            border-radius: 16px;
            background: #F8F9FA;
            border: 1px solid var(--line);
        }

        .age-metric strong {
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
            font-size: 40px;
        }

        .milestone-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .milestone-group {
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 14px;
        }

        .milestone-group h3 {
            margin: 0 0 10px;
            font-size: 18px;
        }

        .milestone-check {
            display: flex;
            align-items: flex-start;
            gap: 9px;
            margin: 9px 0;
            font-weight: 500;
        }

        .progress-track {
            height: 14px;
            overflow: hidden;
            border-radius: 999px;
            background: #E9ECEF;
        }

        .progress-fill {
            height: 100%;
            width: {{ progress_percent }}%;
            background: var(--rose-pink);
        }

        .safety-guide-bar {
            display: flex;
            gap: 16px;
            align-items: center;
            margin-top: 28px;
        }

        .safety-guide-bar strong {
            flex: 0 0 auto;
            color: var(--sky-blue);
            font-family: 'Quicksand', sans-serif;
        }

        .error {
            margin-top: 14px;
            border-radius: 16px;
            padding: 14px 16px;
            background: #FFF1F4;
            color: var(--charcoal);
            border: 1px solid #F7C5D0;
        }

        @media (max-width: 860px) {
            .search-row,
            .empty-state,
            .agent-overview,
            .mission-grid,
            .recommendation-grid,
            .profile-grid,
            .profile-memory-grid,
            .verified-grid,
            .seo-link-grid,
            .milestone-grid,
            .safety-guide-bar {
                grid-template-columns: 1fr;
            }

            .safety-guide-bar,
            .trust-disclosure {
                display: grid;
            }
        }
    </style>
</head>
<body>
    <main>
        <header class="hero-header">
            <div class="logo-mark">N</div>
            <h1 class="nurture-title">Nurture</h1>
            <p class="section-kicker">Trusted parent commerce advisor for developmental progress, safety, and shopping.</p>
        </header>
        {{ guide_panel|safe }}

        <form method="post">
            <section class="intake-shell">
                <h2>Start with the child and the goal</h2>
                <p class="muted">Enter the age and a milestone, toy, or clean-swap question. Nurture will respond first, then recommend commerce-ready picks.</p>
                <div class="search-panel">
                    <div class="search-row">
                        <label>
                            Search intent or clean-swap check
                            <input type="text" name="user_input" value="{{ user_input }}" placeholder="Paste a toy name, Amazon link, or milestone goal">
                        </label>
                        <label>
                            Birth date
                            <input type="date" name="birth_date" value="{{ birth_date }}">
                        </label>
                        <button type="submit">Analyze</button>
                    </div>
                </div>
                {% if error %}
                    <div class="error">{{ error }}</div>
                {% endif %}
                <details class="setup-drawer">
                    <summary>Personalize Nurture's advice</summary>
                    {{ advisor_profile|safe }}
                </details>
                <details class="setup-drawer">
                    <summary>Track milestones and progress</summary>
                    {{ growth_tracker|safe }}
                </details>
            </section>
        </form>

        {% if has_results %}
            <section class="results-workspace">
                {{ scout_response|safe }}
                <div class="result-tabs">
                    <input type="radio" name="result_tab" id="tab-recommendations" checked>
                    <input type="radio" name="result_tab" id="tab-safety">
                    <input type="radio" name="result_tab" id="tab-missions">
                    <input type="radio" name="result_tab" id="tab-clean-swap">
                    <input type="radio" name="result_tab" id="tab-profile">
                    <input type="radio" name="result_tab" id="tab-verified">
                    <input type="radio" name="result_tab" id="tab-weekly">
                    <input type="radio" name="result_tab" id="tab-guides">

                    <div class="tab-labels" role="tablist" aria-label="Nurture result features">
                        <label for="tab-recommendations">Recommendations</label>
                        <label for="tab-safety">Safety</label>
                        <label for="tab-missions">Missions</label>
                        <label for="tab-clean-swap">Clean Swap</label>
                        <label for="tab-profile">Profile</label>
                        <label for="tab-verified">Verified Picks</label>
                        <label for="tab-weekly">Weekly Brief</label>
                        <label for="tab-guides">Guides</label>
                    </div>

                    <div class="tab-panels">
                        <section class="tab-panel recommendations-panel">
                            <div class="recommendation-grid">
                                {{ recommendation_cards|safe }}
                            </div>
                            <div class="report-actions">
                                <button type="button" id="copy-report-button" class="secondary-action">Copy parent report</button>
                                <span id="copy-report-status" aria-live="polite"></span>
                            </div>
                        </section>
                        <section class="tab-panel safety-panel">
                            <section class="tab-panel-card">
                                <span class="agent-label">Nurture Safety Score</span>
                                <h3>Safety is scored inside each product card</h3>
                                <p>Open "Safety score and reasoning" on a recommendation to see age fit, material quality, small-parts concern, brand trust, developmental match, and overstimulation risk.</p>
                            </section>
                        </section>
                        <section class="tab-panel missions-panel">
                            {{ mission_cards|safe }}
                        </section>
                        <section class="tab-panel clean-swap-panel">
                            {{ clean_swap_panel|safe }}
                        </section>
                        <section class="tab-panel profile-panel-tab">
                            {{ growth_tracker|safe }}
                        </section>
                        <section class="tab-panel verified-panel">
                            {{ verified_catalog|safe }}
                        </section>
                        <section class="tab-panel weekly-panel">
                            {{ weekly_brief_panel|safe }}
                        </section>
                        <section class="tab-panel guides-panel">
                            {{ seo_links|safe }}
                        </section>
                    </div>
                </div>
            </section>
        {% else %}
            <section class="empty-state">
                <article class="empty-state-card">
                    <span class="agent-label">Step 1</span>
                    <h3>Ask Nurture</h3>
                    <p>Start with age plus a milestone, toy name, or Amazon link.</p>
                </article>
                <article class="empty-state-card">
                    <span class="agent-label">Step 2</span>
                    <h3>Get the scout read</h3>
                    <p>Nurture identifies the developmental pattern before shopping.</p>
                </article>
                <article class="empty-state-card">
                    <span class="agent-label">Step 3</span>
                    <h3>Shop with trust</h3>
                    <p>Recommendations include safety scoring, clean-swap logic, and affiliate links.</p>
                </article>
            </section>
        {% endif %}

        <details class="feature-drawer">
            <summary>Trust, affiliate disclosure, and shopping guides</summary>
            {{ affiliate_disclosure|safe }}
            <section class="safety-guide-bar">
                <strong>Safe Materials Guide</strong>
                <span>We prioritize wood, organic cotton, food-grade silicone, and water-based finishes because toddlers explore with their hands and mouths. Recommendations favor non-toxic finishes, durable construction, simple sensory feedback, and transparent brands.</span>
            </section>
            {{ seo_links|safe }}
        </details>
    </main>
    <script>
        const memoryFields = document.querySelectorAll("[data-memory-key]");
        memoryFields.forEach((field) => {
            const key = "nurture_profile_" + field.dataset.memoryKey;
            const savedValue = localStorage.getItem(key);
            if (savedValue !== null && !field.value) {
                if (field.type === "checkbox") {
                    field.checked = savedValue === "true";
                } else {
                    field.value = savedValue;
                }
            }
            field.addEventListener("input", () => {
                localStorage.setItem(key, field.type === "checkbox" ? String(field.checked) : field.value);
            });
            field.addEventListener("change", () => {
                localStorage.setItem(key, field.type === "checkbox" ? String(field.checked) : field.value);
            });
        });

        document.querySelectorAll("[data-track-action]").forEach((element) => {
            element.addEventListener("click", () => {
                fetch("/event", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        action: element.dataset.trackAction,
                        title: element.dataset.trackTitle || "",
                    }),
                }).catch(() => {});
            });
        });

        const copyReportButton = document.getElementById("copy-report-button");
        if (copyReportButton) {
            copyReportButton.addEventListener("click", async () => {
                const status = document.getElementById("copy-report-status");
                const reportText = [
                    "Nurture Parent Report",
                    document.querySelector(".hero-header")?.innerText || "",
                    document.querySelector(".scout-response")?.innerText || "",
                    document.querySelector(".mission-section")?.innerText || "",
                    document.querySelector(".recommendation-grid")?.innerText || "",
                ].filter(Boolean).join("\\n\\n");
                try {
                    await navigator.clipboard.writeText(reportText);
                    if (status) status.textContent = "Report copied";
                    fetch("/event", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({action: "copy_report", title: "Parent report"}),
                    }).catch(() => {});
                } catch {
                    if (status) status.textContent = "Copy failed";
                }
            });
        }
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    raw_birth_date = request.form.get("birth_date") or default_birth_date_for_age().isoformat()
    birth_date = parse_birth_date(raw_birth_date)
    months = calculate_months(birth_date)
    user_input = request.form.get("user_input", "")
    profile = get_profile_from_request()
    seen_milestones = set(request.form.getlist("seen_milestones"))
    checked_count, total_count = get_nurture_progress(seen_milestones)
    progress_percent = round((checked_count / total_count) * 100) if total_count else 0
    milestone_checkboxes = render_milestone_checkboxes(seen_milestones)
    scout_response = ""
    clean_swap_panel = ""
    weekly_brief_panel = ""
    mission_cards = ""
    recommendation_cards = ""
    subscription_notice = ""
    error = ""

    if request.method == "POST" and profile["email"] and profile["subscribe_weekly"]:
        append_jsonl(
            LEAD_LOG_PATH,
            {
                "type": "weekly_brief_signup",
                "email": profile["email"],
                "child_age_months": months,
                "interests": profile["interests"],
                "budget": profile["budget"],
            },
        )
        subscription_notice = '<div class="subscription-notice">Weekly brief saved for this browser session. Email sending is ready for a provider integration.</div>'

    if request.method == "POST" and user_input.strip():
        try:
            insights = get_nurture_agent_response(user_input.strip(), months, seen_milestones, profile)
            scout_response = render_scout_response(insights)
            clean_swap_panel = render_clean_swap_panel(insights)
            weekly_brief_panel = render_weekly_brief_panel(insights)
            mission_cards = render_mission_cards(insights["missions"])
            recommendation_cards = render_recommendations_grid(insights["recommendations"], months)
        except Exception as exc:
            error = str(exc)

    growth_tracker = render_growth_tracker(
        months,
        checked_count,
        total_count,
        progress_percent,
        milestone_checkboxes,
    )
    has_results = bool(scout_response or recommendation_cards or mission_cards)

    return render_template_string(
        PAGE_TEMPLATE,
        advisor_profile=render_advisor_profile(profile, subscription_notice),
        affiliate_disclosure=render_affiliate_disclosure(),
        birth_date=birth_date.isoformat(),
        checked_count=checked_count,
        clean_swap_panel=clean_swap_panel,
        error=error,
        growth_tracker=growth_tracker,
        guide_panel="",
        has_results=has_results,
        mission_cards=mission_cards,
        milestone_checkboxes=milestone_checkboxes,
        months=months,
        progress_percent=progress_percent,
        recommendation_cards=recommendation_cards,
        scout_response=scout_response,
        seo_description="Nurture connects developmental progress, toy safety, and trustworthy shopping for parents of children from 0 to 3.",
        seo_links=render_seo_links(),
        seo_title="Nurture | Trusted Parent Commerce Advisor",
        total_count=total_count,
        user_input=user_input,
        verified_catalog=render_verified_catalog(months, profile["avoided_materials"]),
        weekly_brief_panel=weekly_brief_panel,
    )


@app.route("/event", methods=["POST"])
def track_event():
    payload = request.get_json(silent=True) or {}
    append_jsonl(
        EVENT_LOG_PATH,
        {
            "type": "ui_event",
            "action": clean_text(payload.get("action")),
            "title": clean_text(payload.get("title")),
            "path": request.referrer or "",
        },
    )
    return jsonify({"ok": True})


@app.route("/go")
def go_to_amazon():
    target_url = clean_text(request.args.get("url"))
    title = clean_text(request.args.get("title"))
    if not is_amazon_product_url(target_url):
        return redirect("/")

    append_jsonl(
        EVENT_LOG_PATH,
        {
            "type": "amazon_outbound_click",
            "title": title,
            "url": target_url,
        },
    )
    return redirect(target_url)


@app.route("/guides/<slug>")
def guide(slug):
    guide_data = SEO_GUIDES.get(slug)
    if not guide_data:
        return redirect("/")

    birth_date = default_birth_date_for_age()
    months = calculate_months(birth_date)
    profile = {
        "child_name": "",
        "interests": "",
        "budget": "",
        "avoided_materials": "",
        "gift_occasion": "",
        "email": "",
        "subscribe_weekly": False,
    }
    checked_count, total_count = get_nurture_progress(set())
    progress_percent = round((checked_count / total_count) * 100) if total_count else 0
    milestone_checkboxes = render_milestone_checkboxes(set())
    growth_tracker = render_growth_tracker(
        months,
        checked_count,
        total_count,
        progress_percent,
        milestone_checkboxes,
    )

    return render_template_string(
        PAGE_TEMPLATE,
        advisor_profile=render_advisor_profile(profile, ""),
        affiliate_disclosure=render_affiliate_disclosure(),
        birth_date=birth_date.isoformat(),
        checked_count=checked_count,
        clean_swap_panel="",
        error="",
        growth_tracker=growth_tracker,
        guide_panel=render_guide_panel(slug),
        has_results=False,
        mission_cards="",
        milestone_checkboxes=milestone_checkboxes,
        months=months,
        progress_percent=progress_percent,
        recommendation_cards="",
        scout_response="",
        seo_description=guide_data["description"],
        seo_links=render_seo_links(),
        seo_title=f"{guide_data['title']} | Nurture",
        total_count=total_count,
        user_input=guide_data["title"],
        verified_catalog=render_verified_catalog(months, ""),
        weekly_brief_panel="",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
