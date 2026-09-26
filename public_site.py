"""Public discovery plus optional Supabase accounts and child profiles."""
from dataclasses import replace
import hmac
import secrets

from flask import (Blueprint, abort, current_app, g, redirect, render_template,
    request, session as flask_session, url_for)

from accounts import (AUTH, FEATURES, PROFILES, AccountServiceError, ChildProfile,
    Session as AccountSession)
from activity_catalog import FixtureCatalog, KIT_PREVIEWS
from discovery import (AGE_BANDS, BUDGETS, CATEGORIES, CATEGORY_LABELS, INTERESTS, KINDS,
    SETTINGS, TIMES, SearchPreferences, filter_activities, filter_chips, parse_preferences,
    preference_url, recommend)

site = Blueprint("site", __name__)
catalog = FixtureCatalog()


def csrf_token() -> str:
    token = flask_session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        flask_session["csrf_token"] = token
    return token


def valid_csrf() -> bool:
    expected = flask_session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def current_account() -> AccountSession | None:
    if "nurture_account" not in g:
        try:
            g.nurture_account = AUTH.current_session() if FEATURES["auth"] else None
        except AccountServiceError:
            g.nurture_account = None
    return g.nurture_account


def require_account():
    if not FEATURES["auth"]:
        return None, (render_template("auth.html", signup=False, dashboard_denied=True,
            configured=False), 401)
    account = current_account()
    if not account:
        return None, redirect("/login")
    return account, None


@site.app_errorhandler(404)
def not_found(error):
    return render_template("error.html"), 404


@site.context_processor
def shared_context():
    return dict(features=FEATURES, account_session=current_account(), csrf_token=csrf_token,
        categories=CATEGORIES, age_bands={k: v[2] for k, v in AGE_BANDS.items()},
        kinds=KINDS, interests=INTERESTS, times=TIMES, budgets=BUDGETS,
        settings=SETTINGS, category_labels=CATEGORY_LABELS)


def discovery_context(full=False):
    p = parse_preferences(request.args)
    matches = filter_activities(catalog.activities(), p)
    path, anchor = ("/explore", "results") if full else ("/", "just-for-you")
    return dict(p=p, activities=matches if full else matches[:4], count=len(matches),
        recommendation=recommend(catalog.activities(), p), chips=filter_chips(p, path, anchor),
        full=full, form_path=path, result_anchor=anchor,
        full_url=preference_url(p, "/explore", "results"),
        category_urls={key: preference_url(replace(p, category=key, submitted=True),
            "/explore", "results") for key in CATEGORY_LABELS}, kit_previews=KIT_PREVIEWS)


@site.get("/")
def home():
    return render_template("home.html", **discovery_context())


@site.get("/explore")
def explore():
    return render_template("explore.html", **discovery_context(True))


@site.get("/activities/<slug>")
def activity_detail(slug):
    activity = next((a for a in catalog.activities() if a.slug == slug), None)
    if not activity:
        abort(404)
    p = parse_preferences(request.args)
    return render_template("activity_detail.html", activity=activity,
        back_url=preference_url(p, "/explore", "results"))


@site.route("/login", methods=["GET", "POST"])
@site.route("/get-started", methods=["GET", "POST"])
def auth_entry():
    signup = request.path == "/get-started"
    if request.method == "GET":
        return render_template("auth.html", signup=signup, configured=FEATURES["auth"])
    if not FEATURES["auth"]:
        return render_template("auth.html", signup=signup, configured=False), 405
    if not valid_csrf():
        return render_template("auth.html", signup=signup, configured=True,
            error="Your form expired. Refresh and try again."), 400
    email, password = request.form.get("email", ""), request.form.get("password", "")
    try:
        result = AUTH.sign_up(email, password) if signup else AUTH.sign_in(email, password)
    except ValueError as exc:
        return render_template("auth.html", signup=signup, configured=True,
            error=str(exc), email=email), 400
    except AccountServiceError as exc:
        return render_template("auth.html", signup=signup, configured=True,
            error=str(exc), email=email), 503
    if result.status == "signed_in":
        return redirect(url_for("site.profile_setup" if signup else "site.dashboard"), code=303)
    if result.status == "verification_required":
        return render_template("auth.html", signup=False, configured=True,
            status_message=result.message, email=email)
    return render_template("auth.html", signup=signup, configured=True,
        error=result.message, email=email), 400


@site.post("/logout")
def logout():
    if not valid_csrf():
        abort(400)
    try:
        AUTH.sign_out()
    except AccountServiceError:
        # Local session should still be cleared by the provider when possible.
        pass
    return redirect(url_for("site.home"), code=303)


def profile_from_form(account: AccountSession) -> ChildProfile:
    nickname = request.form.get("nickname", "").strip()
    age_band = request.form.get("age_band", "")
    setting = request.form.get("setting", "")
    if len(nickname) > 40:
        raise ValueError("Nickname must be 40 characters or fewer.")
    if age_band not in AGE_BANDS:
        raise ValueError("Choose an age band.")
    if setting and setting not in SETTINGS:
        raise ValueError("Choose a valid setting preference.")
    selected = set(request.form.getlist("interests"))
    interests = tuple(key for key in INTERESTS if key in selected)
    return ChildProfile(account.account_id, nickname, age_band, interests, setting)


@site.route("/profile", methods=["GET", "POST"])
def profile_setup():
    account, denied = require_account()
    if denied:
        return denied
    try:
        profile = PROFILES.get(account)
    except AccountServiceError as exc:
        return render_template("profile.html", profile=None, error=str(exc)), 503
    if request.method == "POST":
        if not valid_csrf():
            return render_template("profile.html", profile=profile,
                error="Your form expired. Refresh and try again."), 400
        try:
            profile = PROFILES.save(account, profile_from_form(account))
        except ValueError as exc:
            return render_template("profile.html", profile=profile, error=str(exc)), 400
        except AccountServiceError as exc:
            return render_template("profile.html", profile=profile, error=str(exc)), 503
        return redirect(url_for("site.dashboard"), code=303)
    return render_template("profile.html", profile=profile)


@site.get("/dashboard")
def dashboard():
    account, denied = require_account()
    if denied:
        return denied
    try:
        profile = PROFILES.get(account)
    except AccountServiceError as exc:
        return render_template("dashboard.html", account=account, profile=None,
            activities=(), profile_error=str(exc)), 503
    if not profile:
        return redirect(url_for("site.profile_setup"), code=303)
    preferences = SearchPreferences(age=profile.age_band, interests=profile.interests,
        setting=profile.setting, submitted=True)
    activities = filter_activities(catalog.activities(), preferences)[:4]
    return render_template("dashboard.html", account=account, profile=profile,
        activities=activities, profile_error=None)


@site.get("/dev/dashboard")
def dashboard_preview():
    if not (current_app.debug and current_app.config.get("NURTURE_DEV_PREVIEW", False)):
        abort(404)
    demo = ChildProfile("development", "Sunny", "3-4", ("art", "nature"), "")
    return render_template("dashboard.html", account=None, profile=demo,
        activities=catalog.activities()[:4], profile_error=None, development_preview=True)


@site.app_template_global()
def detail_url(activity, p=None):
    return preference_url(p or SearchPreferences(),
        url_for("site.activity_detail", slug=activity.slug), "")
