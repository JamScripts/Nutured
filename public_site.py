"""Milestone 1 public Flask routes; existing advisor routes remain in app.py."""
from dataclasses import replace
from flask import Blueprint, abort, current_app, render_template, request, url_for
from accounts import AUTH, FEATURES
from activity_catalog import FixtureCatalog, KIT_PREVIEWS
from discovery import (AGE_BANDS, BUDGETS, CATEGORIES, CATEGORY_LABELS, INTERESTS, KINDS,
    SETTINGS, TIMES, SearchPreferences, filter_activities, filter_chips, parse_preferences,
    preference_url, recommend)

site = Blueprint("site", __name__)
catalog = FixtureCatalog()

@site.app_errorhandler(404)
def not_found(error):
    return render_template("error.html"), 404

@site.context_processor
def shared_context():
    return dict(features=FEATURES, session=AUTH.current_session(), categories=CATEGORIES,
        age_bands={k:v[2] for k,v in AGE_BANDS.items()}, kinds=KINDS, interests=INTERESTS,
        times=TIMES, budgets=BUDGETS, settings=SETTINGS, category_labels=CATEGORY_LABELS)

def discovery_context(full=False):
    p = parse_preferences(request.args)
    matches = filter_activities(catalog.activities(), p)
    path, anchor = ("/explore", "results") if full else ("/", "just-for-you")
    return dict(p=p, activities=matches if full else matches[:4], count=len(matches),
        recommendation= recommend(catalog.activities(), p),
        chips=filter_chips(p, path, anchor), full=full, form_path=path, result_anchor=anchor,
        full_url=preference_url(p, "/explore", "results"),
        category_urls={key: preference_url(replace(p, category=key, submitted=True), "/explore", "results") for key in CATEGORY_LABELS},
        kit_previews=KIT_PREVIEWS)

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
        back_url=preference_url(p,"/explore","results"))

@site.get("/login")
@site.get("/get-started")
def auth_entry():
    return render_template("auth.html", signup=request.path == "/get-started"), 200

@site.get("/dashboard")
def dashboard():
    # Denied on the server, including forged cookies/query strings. No private
    # profile lookup or data is available through this unavailable provider.
    return render_template("auth.html", signup=False, dashboard_denied=True), 401

@site.get("/dev/dashboard")
def dashboard_preview():
    if not (current_app.debug and current_app.config.get("NURTURE_DEV_PREVIEW", False)):
        abort(404)
    return render_template("dashboard.html", activities=catalog.activities()[:4])

@site.app_template_global()
def detail_url(activity, p=None):
    return preference_url(p or SearchPreferences(), url_for("site.activity_detail", slug=activity.slug), "")
