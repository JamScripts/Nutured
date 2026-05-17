import html
import json
import os
from calendar import monthrange
from datetime import date
from urllib.parse import quote_plus, urlparse

from flask import Flask, render_template_string, request
from openai import OpenAI

from milestones import format_milestones_for_prompt, get_relevant_cdc_milestones


app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AMAZON_ID = os.environ.get("AMAZON_ID", "steppingstone-20")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

APPROVED_AMAZON_IMAGE_SOURCES = {"amazon_creators_api", "amazon_pa_api"}
AMAZON_IMAGE_HOSTS = {"m.media-amazon.com", "images-na.ssl-images-amazon.com"}
AMAZON_PRODUCT_HOSTS = {"amazon.com", "www.amazon.com", "smile.amazon.com"}


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
        escaped_product_url = html.escape(product_url, quote=True)
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


def normalize_recommendation(recommendation):
    title = recommendation.get("title") or recommendation.get("name") or "Developmental Gift"
    brand = recommendation.get("brand") or "Clean-swap pick"
    milestone = recommendation.get("cdc_milestone") or recommendation.get("milestone_logic") or "CDC milestone"
    why_it_matters = recommendation.get("why_it_matters") or recommendation.get("description") or ""
    confidence_label = recommendation.get("confidence_label") or recommendation.get("confidence") or "Good next step"
    timeline = recommendation.get("timeline") if isinstance(recommendation.get("timeline"), dict) else {}
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

    return {
        "title": str(title),
        "brand": str(brand),
        "cdc_milestone": str(milestone),
        "confidence_label": str(confidence_label),
        "timeline": {
            "current_milestone": str(timeline.get("current_milestone") or milestone),
            "skill_strengthened": str(timeline.get("skill_strengthened") or "Targeted developmental practice"),
            "recommended_toy": str(timeline.get("recommended_toy") or title),
            "what_to_observe": str(timeline.get("what_to_observe") or "Watch for curiosity, repetition, and small gains in independence."),
        },
        "why_it_matters": str(why_it_matters),
        "search_query": str(search_query),
        "image_alt": str(recommendation.get("image_alt") or title),
        "image_source": image_source,
        "image_url": image_url,
        "amazon_product_url": amazon_product_url,
    }


def normalize_mission(mission):
    return {
        "title": str(mission.get("title") or mission.get("mission") or "This week's mission: Practice a new skill"),
        "activity": str(mission.get("activity") or "Build one short play routine around this skill."),
        "toy_connection": str(mission.get("toy_connection") or "Use a simple, clean-material toy that invites repetition."),
        "what_to_watch": str(mission.get("what_to_watch") or "Watch for attempts, imitation, and confidence."),
    }


def normalize_agent_payload(payload):
    if not isinstance(payload, dict):
        payload = {}

    clean_swap_review = payload.get("clean_swap_review")
    if not isinstance(clean_swap_review, dict):
        clean_swap_review = {}

    missions = payload.get("missions") or payload.get("mission_cards") or []
    if not isinstance(missions, list):
        missions = []

    recommendations = payload.get("recommendations") or []
    if not isinstance(recommendations, list):
        recommendations = []

    return {
        "scout_summary": str(payload.get("scout_summary") or payload.get("summary") or ""),
        "weekly_brief": str(payload.get("weekly_brief") or ""),
        "clean_swap_review": {
            "verdict": str(clean_swap_review.get("verdict") or ""),
            "reason": str(clean_swap_review.get("reason") or ""),
            "swap_strategy": str(clean_swap_review.get("swap_strategy") or ""),
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


def render_recommendations_grid(recommendations):
    normalized_recommendations = [normalize_recommendation(item) for item in recommendations[:3]]
    cards = []

    for index, recommendation in enumerate(normalized_recommendations):
        title = html.escape(recommendation["title"])
        brand = html.escape(recommendation["brand"])
        milestone = html.escape(recommendation["cdc_milestone"])
        confidence_label = html.escape(recommendation["confidence_label"])
        timeline = recommendation["timeline"]
        why_it_matters = html.escape(recommendation["why_it_matters"])
        amazon_url = html.escape(build_amazon_search_url(recommendation["search_query"]), quote=True)
        product_visual = render_product_visual(recommendation, amazon_url)
        badge = '<span class="top-pick-badge">TOP PICK</span>' if index == 0 else ""

        cards.append(
            f"""
            <article class="product-recommendation-card">
                {badge}
                {product_visual}
                <div class="card-brand">{brand}</div>
                <h3>{title}</h3>
                <span class="confidence-label">{confidence_label}</span>
                <div class="why-it-matters">
                    <strong>Why it Matters</strong>
                    <p>{why_it_matters}</p>
                    <p><strong>CDC milestone:</strong> {milestone}</p>
                </div>
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
                <div class="marketplace-button-row">
                    <a class="marketplace-button" href="{amazon_url}" target="_blank" rel="noopener noreferrer">
                        View on Amazon
                    </a>
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


def get_nurture_agent_response(user_input, child_age, seen_milestones):
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your Railway environment variables.")

    milestone_context = format_milestones_for_prompt(child_age)
    required_milestones = build_required_milestone_context(child_age)
    seen_milestone_context = (
        "\n".join(f"- {milestone}" for milestone in sorted(seen_milestones))
        if seen_milestones
        else "- No milestones checked today."
    )
    system_prompt = f"""
    You are Nurture, an expert child development scout and clean-swap toy agent.
    The child is {child_age} months old.

    Use this CDC milestone context as the source of truth:
    {milestone_context}

    Required CDC milestone phrases to consider:
    {required_milestones}

    Milestones the parent checked today:
    {seen_milestone_context}

    Agent behavior:
    - Start with Nurture Scout Mode: infer the developmental pattern behind the user's request.
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
    <title>Nurture</title>
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

        .marketplace-button-row {
            margin-top: 18px;
            text-align: center;
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
            .agent-overview,
            .mission-grid,
            .recommendation-grid,
            .profile-grid,
            .milestone-grid,
            .safety-guide-bar {
                grid-template-columns: 1fr;
            }

            .safety-guide-bar {
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
            <p class="section-kicker">Your personal developmental gift scout.</p>
        </header>

        <form method="post">
            <section>
                <h2>Amazon Gift Recommendations</h2>
                <p class="muted">Describe the skill, milestone, or gift search you have in mind.</p>
                <div class="search-panel">
                    <div class="search-row">
                        <label>
                            Search intent
                            <input type="text" name="user_input" value="{{ user_input }}" placeholder="Find wooden toys for spoon practice">
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
                {% if agent_overview %}
                    {{ agent_overview|safe }}
                {% endif %}
                {% if mission_cards %}
                    {{ mission_cards|safe }}
                {% endif %}
                {% if recommendation_cards %}
                    <div class="recommendation-grid">
                        {{ recommendation_cards|safe }}
                    </div>
                {% endif %}
            </section>

            <section>
                <h2>Child Profile & Milestones</h2>
                <div class="profile-grid">
                    <div class="age-metric">
                        <span>Age in months</span>
                        <strong>{{ months }}m</strong>
                    </div>
                    <div class="profile-panel">
                        <div class="milestone-grid">
                            {{ milestone_checkboxes|safe }}
                        </div>
                    </div>
                </div>
            </section>

            <section>
                <h2>Developmental Progress</h2>
                <div class="progress-track">
                    <div class="progress-fill"></div>
                </div>
                <p class="muted">{{ checked_count }} of {{ total_count }} milestones seen today</p>
            </section>
        </form>

        <section class="safety-guide-bar">
            <strong>Safe Materials Guide</strong>
            <span>We prioritize wood, organic cotton, food-grade silicone, and water-based finishes because toddlers explore with their hands and mouths. Recommendations favor non-toxic finishes, durable construction, simple sensory feedback, and transparent brands.</span>
        </section>
    </main>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    raw_birth_date = request.form.get("birth_date") or default_birth_date_for_age().isoformat()
    birth_date = parse_birth_date(raw_birth_date)
    months = calculate_months(birth_date)
    user_input = request.form.get("user_input", "")
    seen_milestones = set(request.form.getlist("seen_milestones"))
    checked_count, total_count = get_nurture_progress(seen_milestones)
    progress_percent = round((checked_count / total_count) * 100) if total_count else 0
    agent_overview = ""
    mission_cards = ""
    recommendation_cards = ""
    error = ""

    if request.method == "POST" and user_input.strip():
        try:
            insights = get_nurture_agent_response(user_input.strip(), months, seen_milestones)
            agent_overview = render_agent_overview(insights)
            mission_cards = render_mission_cards(insights["missions"])
            recommendation_cards = render_recommendations_grid(insights["recommendations"])
        except Exception as exc:
            error = str(exc)

    return render_template_string(
        PAGE_TEMPLATE,
        agent_overview=agent_overview,
        birth_date=birth_date.isoformat(),
        checked_count=checked_count,
        error=error,
        mission_cards=mission_cards,
        milestone_checkboxes=render_milestone_checkboxes(seen_milestones),
        months=months,
        progress_percent=progress_percent,
        recommendation_cards=recommendation_cards,
        total_count=total_count,
        user_input=user_input,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
