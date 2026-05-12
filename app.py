import os
from datetime import date
import html
import json
from urllib.parse import quote_plus

import streamlit as st
from google import genai
from milestones import format_milestones_for_prompt, get_relevant_cdc_milestones


# --- 1. BRANDING & PAGE CONFIG ---
st.set_page_config(page_title="Nurture", page_icon="🧩", layout="wide")


# --- 2. SECURE KEY & ID FETCH ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
AMAZON_ID = os.environ.get("AMAZON_ID")

if not AMAZON_ID:
    try:
        AMAZON_ID = st.secrets["AMAZON_ID"]
    except Exception:
        AMAZON_ID = "steppingstone-20"


# --- 3. INITIALIZE THE AI AGENT ---
client = None
if GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as init_e:
        st.error(f"Failed to initialize AI Client: {init_e}")
else:
    st.error(
        "🔑 Error: GOOGLE_API_KEY not found. Add it to your Railway environment variables."
    )


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


def get_nurture_progress():
    checked_count = 0
    total_count = sum(len(milestones) for milestones in NURTURE_WEEKLY_MILESTONES.values())

    for category, milestones in NURTURE_WEEKLY_MILESTONES.items():
        for milestone in milestones:
            key = f"nurture_{category}_{milestone}"
            if st.session_state.get(key):
                checked_count += 1

    return checked_count, total_count


def render_nurture_milestones(age_months, container):
    container.header("Nurture Milestones")
    container.caption(f"Weekly growth tracker for {age_months} months")

    for category, milestones in NURTURE_WEEKLY_MILESTONES.items():
        container.subheader(category)
        for milestone in milestones:
            key = f"nurture_{category}_{milestone}"
            container.checkbox(milestone, key=key)


def render_safety_guide_bar():
    st.markdown(
        """
        <div class="safety-guide-bar">
            <strong>Safe Materials Guide</strong>
            <span>We prioritize wood, organic cotton, food-grade silicone, and water-based finishes because toddlers explore with their hands and mouths. Recommendations favor non-toxic finishes, durable construction, simple sensory feedback, and transparent brands.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        raise ValueError("Gemini did not return a JSON object.")

    return json.loads(cleaned[start : end + 1])


def build_amazon_search_url(search_query):
    return f"https://www.amazon.com/s?k={quote_plus(search_query)}&tag={quote_plus(AMAZON_ID)}"


def render_marketplace_cards(recommendations):
    columns = st.columns(3)

    for index, column in enumerate(columns):
        if index >= len(recommendations):
            column.empty()
            continue

        recommendation = recommendations[index]
        title = html.escape(str(recommendation.get("title", "Developmental Gift")))
        brand = html.escape(str(recommendation.get("brand", "Curated pick")))
        milestone = html.escape(str(recommendation.get("cdc_milestone", "CDC milestone")))
        why_it_matters = html.escape(str(recommendation.get("why_it_matters", "")))
        search_query = str(recommendation.get("search_query") or recommendation.get("title") or title)
        amazon_url = html.escape(build_amazon_search_url(search_query), quote=True)
        badge = '<span class="top-pick-badge">TOP PICK</span>' if index == 0 else ""

        column.markdown(
            f"""
            <div class="product-recommendation-card">
                {badge}
                <div class="card-brand">{brand}</div>
                <h3>{title}</h3>
                <div class="why-it-matters">
                    <strong>Why it Matters</strong>
                    <p>{why_it_matters}</p>
                    <p><strong>CDC milestone:</strong> {milestone}</p>
                </div>
                <div class="marketplace-button-row">
                    <a class="marketplace-button" href="{amazon_url}" target="_blank" rel="noopener noreferrer">
                        View on Amazon
                    </a>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


NURTURE_THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Quicksand:wght@600;700&display=swap');

    #MainMenu,
    footer,
    [data-testid="stToolbar"],
    .stDeployButton {
        visibility: hidden;
        height: 0;
    }

    .stApp {
        background: #F8F9FA;
        color: #2C3E50;
    }

    .stApp,
    .stMarkdown,
    [data-testid="stWidgetLabel"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    p,
    li,
    span,
    label {
        font-family: 'Inter', sans-serif;
        color: #2C3E50;
    }

    h1,
    h2,
    h3,
    .nurture-title {
        font-family: 'Quicksand', sans-serif !important;
        color: #87CEEB !important;
        letter-spacing: 0;
    }

    .nurture-title {
        margin: 0 0 0.2rem;
        font-size: 3.45rem;
        line-height: 1.05;
        font-weight: 700;
        text-align: center;
    }

    .section-kicker {
        margin-bottom: 1.5rem;
        color: #2C3E50;
        font-size: 1.02rem;
        text-align: center;
    }

    .hero-header {
        margin: 0 auto 2rem;
        max-width: 54rem;
        text-align: center;
    }

    .logo-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 3.2rem;
        height: 3.2rem;
        margin-bottom: 0.45rem;
        border-radius: 50%;
        background: #FFFFFF;
        color: #87CEEB;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        font-size: 1.75rem;
    }

    .stButton > button {
        width: 100%;
        border: 0;
        border-radius: 8px;
        background: #F497AD;
        color: #ffffff;
        font-family: 'Quicksand', sans-serif;
        font-weight: 700;
        box-shadow: 0 12px 28px rgba(244, 151, 173, 0.28);
        transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
    }

    .stButton > button:hover {
        background: #ef819d;
        color: #ffffff;
        transform: translateY(-2px);
        box-shadow: 0 16px 34px rgba(244, 151, 173, 0.34);
    }

    .stProgress > div > div > div > div {
        background-color: #F497AD;
    }

    .product-recommendation-card {
        position: relative;
        min-height: 25rem;
        margin: 1rem 0;
        padding: 20px;
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        transition: transform 180ms ease, box-shadow 180ms ease;
    }

    .product-recommendation-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 14px 30px rgba(0,0,0,0.1);
    }

    .product-recommendation-card h3 {
        min-height: 3.2rem;
        margin: 2rem 0 0.65rem;
        color: #87CEEB;
        font-family: 'Quicksand', sans-serif;
        font-size: 1.28rem;
        line-height: 1.25;
    }

    .product-recommendation-card a {
        color: #F497AD;
        font-weight: 700;
    }

    .top-pick-badge {
        position: absolute;
        top: 14px;
        right: 14px;
        display: inline-block;
        border-radius: 4px;
        padding: 0.26rem 0.62rem;
        background: #F497AD;
        color: #ffffff;
        font-family: 'Quicksand', sans-serif;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
    }

    .card-brand {
        color: #64747a;
        font-size: 0.88rem;
        font-weight: 700;
        text-transform: uppercase;
    }

    .why-it-matters {
        margin-top: 1rem;
        padding-top: 0.9rem;
        border-top: 1px solid rgba(135, 206, 235, 0.38);
    }

    .why-it-matters strong {
        color: #244a54;
    }

    .marketplace-button {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        min-width: 11rem;
        margin-top: 1.1rem;
        border-radius: 999px;
        padding: 0.72rem 1rem;
        background: #F497AD;
        color: #ffffff !important;
        font-family: 'Quicksand', sans-serif;
        font-weight: 700;
        text-decoration: none !important;
        box-shadow: 0 10px 24px rgba(244, 151, 173, 0.26);
    }

    .marketplace-button:hover {
        background: #ef819d;
    }

    .marketplace-button-row {
        text-align: center;
    }

    .safety-guide-bar {
        display: flex;
        gap: 1rem;
        align-items: center;
        margin-top: 2rem;
        padding: 1rem 1.2rem;
        border: 1px solid #E0E0E0;
        border-radius: 20px;
        background-color: #FFFFFF;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        color: #2C3E50;
    }

    .safety-guide-bar strong {
        flex: 0 0 auto;
        color: #87CEEB;
        font-family: 'Quicksand', sans-serif;
    }
</style>
"""


# --- 4. USER INTERFACE (UI) ---
st.markdown(NURTURE_THEME_CSS, unsafe_allow_html=True)
st.markdown(
    """
    <div class="hero-header">
        <div class="logo-mark">🧩</div>
        <h1 class="nurture-title"><strong>Nurture</strong></h1>
        <p class="section-kicker">Your personal developmental gift scout.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "child_birth_date" not in st.session_state:
    st.session_state.child_birth_date = date(2024, 11, 1)

months = calculate_months(st.session_state.child_birth_date)


# --- 5. AMAZON GIFT RECOMMENDATIONS ---
st.header("Amazon Gift Recommendations")
st.caption("CDC-informed gift ideas for the next developmental step.")

if st.button("Analyze Milestones & Find Gifts"):
    if not client:
        st.warning(
            "Agent brain is offline. Set GOOGLE_API_KEY in Railway environment variables."
        )
    else:
        milestone_context = format_milestones_for_prompt(months)
        required_milestones = build_required_milestone_context(months)
        prompt_text = f"""
        You are Nurture, an expert in child development and clean-swap toy curation.
        The child is {months} months old.

        Use this CDC milestone context as the source of truth. Mention the relevant CDC
        milestone(s) explicitly before recommending gifts, and do not replace them with invented
        milestones.

        {milestone_context}

        Required CDC milestone phrases: In your first section, mention each of these exact phrases:
        {required_milestones}

        Return only valid JSON. Do not wrap it in markdown.
        Use this exact shape:
        {{
          "milestones": ["CDC milestone phrase", "CDC milestone phrase"],
          "recommendations": [
            {{
              "title": "Product search title",
              "brand": "Brand or material category",
              "cdc_milestone": "Exact CDC milestone phrase from the context",
              "why_it_matters": "One concise sentence linking the toy to that CDC milestone.",
              "search_query": "Amazon search query"
            }}
          ]
        }}

        Requirements:
        - Return exactly 3 recommendations.
        - Focus on high-quality, non-toxic, wooden, organic, or food-grade silicone items.
        - Each recommendation must explicitly connect to one CDC milestone in "why_it_matters".
        - Use brands such as Lovevery, Hape, PlanToys, Melissa & Doug, or comparable clean-material brands.
        """

        with st.spinner("Nurture is analyzing developmental data..."):
            last_error = None
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt_text,
                )
                payload = extract_json_payload(response.text or "")
                render_marketplace_cards(payload.get("recommendations", []))
            except Exception as model_error:
                last_error = model_error
                st.error(f"Agent Error: {last_error}")

st.divider()


# --- 6. CHILD PROFILE & MILESTONES ---
st.header("Child's Profile")
profile_columns = st.columns([2, 1])
with profile_columns[0]:
    st.date_input("Birth Date", key="child_birth_date")
months = calculate_months(st.session_state.child_birth_date)
with profile_columns[1]:
    st.metric(label="Age in Months", value=f"{months}m")

with st.expander("Nurture Milestones", expanded=False):
    render_nurture_milestones(months, st)

st.divider()


# --- 7. DEVELOPMENTAL PROGRESS ---
st.header("Developmental Progress")
checked_count, total_count = get_nurture_progress()
st.progress(checked_count / total_count if total_count else 0)
st.caption(f"{checked_count} of {total_count} milestones seen today")
render_safety_guide_bar()
st.caption("Nurture | Building foundations through play.")
