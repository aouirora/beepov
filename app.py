import os
import json
import streamlit as st
import duckdb
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import shapely.wkt
from datetime import datetime
from html import escape
import urllib.parse
# GEOLOCATION FEATURE START
from streamlit_geolocation import streamlit_geolocation
# GEOLOCATION FEATURE END

# ==============================================================================
# DESIGN TOKENS  (charcoal + muted amber — replaces the old yellow theme)
# ==============================================================================
INK      = "#23211D"   # near-black warm charcoal (primary)
INK_2    = "#3A372F"
PAPER    = "#FAF8F3"   # warm off-white surface
LINE     = "#E7E2D7"   # hairline borders
MUTED    = "#8C8578"   # secondary text
ACCENT   = "#B5863C"   # muted amber — the only "bee" colour left
ACCENT_D = "#936B2C"

# Muted, grown-up category colours (used for the hexagon map pins)
CATEGORY_COLORS = {
    "Food & Drink":        "#B07C3A",
    "Nightlife":           "#7E6597",
    "Culture & Heritage":  "#5878A0",
    "Nature & Outdoors":   "#6B8F5E",
    "Public Transport":    "#8C8578",
}

# ==============================================================================
# 0. RATINGS FILE UTILITIES & DIRECT PATH SUBMISSIONS HANDLER
# ==============================================================================
RATINGS_PATH = "data/bee_ratings.json"


@st.cache_data
def load_bee_ratings():
    if not os.path.exists(RATINGS_PATH):
        return {}
    try:
        with open(RATINGS_PATH, "r", encoding="utf-8") as ratings_file:
            ratings = json.load(ratings_file)
            return {key: [int(value) for value in values] for key, values in ratings.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}


def save_bee_rating(place_id, rating):
    ratings = load_bee_ratings()
    ratings.setdefault(place_id, []).append(int(rating))
    os.makedirs(os.path.dirname(RATINGS_PATH), exist_ok=True)
    with open(RATINGS_PATH, "w", encoding="utf-8") as ratings_file:
        json.dump(ratings, ratings_file, indent=2, ensure_ascii=False)
    load_bee_ratings.clear()


# --- Close the right-hand rating panel -----------------------------------------
if "close_panel" in st.query_params:
    st.session_state["clicked_place_id"] = None
    st.query_params.clear()
    st.rerun()

# --- A rating was submitted from the side panel (same-tab link) -----------------
if "rate" in st.query_params and "place_id" in st.query_params:
    try:
        rate_val = int(st.query_params["rate"])
        place_id_val = st.query_params["place_id"]
        save_bee_rating(place_id_val, rate_val)
        # Keep the panel open on the place we just rated so the user sees the update
        st.session_state["clicked_place_id"] = place_id_val
        st.session_state["bee_rating_success"] = f"Thanks! Your {rate_val}-bee rating was added."
    except Exception:
        pass
    st.query_params.clear()
    st.rerun()

# ==============================================================================
# 1. PAGE CONFIG & GLOBAL STYLING
# ==============================================================================
st.set_page_config(
    page_title="beePOV map",
    page_icon="🐝",
    layout="wide",
    initial_sidebar_state="collapsed",   # map reads fullscreen; everything lives in the top bar
)

st.markdown(
    f"""
    <style>
        /* ---------- Layout: trim chrome so the map fills the screen ---------- */
        .block-container {{
            padding: 0.55rem 0.9rem 0 0.9rem;
            max-width: 100%;
        }}
        header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
        #MainMenu, footer {{ visibility: hidden; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        div[data-testid="stToolbar"] {{ display: none; }}

        /* The folium map iframe → near-fullscreen below the top bar */
        iframe[title="streamlit_folium.st_folium"] {{
            height: calc(100vh - 96px) !important;
            min-height: 520px;
            border-radius: 16px;
            border: 1px solid {LINE};
        }}

        /* ---------- App wordmark ---------- */
        .bp-brand {{ display: flex; align-items: center; gap: 0.55rem; }}
        .bp-logo {{
            width: 34px; height: 30px; flex: 0 0 auto;
            clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
            background: {INK};
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
        }}
        .bp-logo span {{ width: 14px; height: 2px; border-radius: 2px; background: {ACCENT}; }}
        .bp-logo span:last-child {{ width: 11px; }}
        .bp-word {{ font-size: 1.35rem; font-weight: 800; letter-spacing: -0.5px; color: {INK}; line-height: 1; }}
        .bp-word b {{ color: {ACCENT}; font-weight: 800; }}

        /* ---------- Subcategory row (under the top bar) ---------- */
        .bp-subhead {{
            font-size: 0.7rem; font-weight: 700; letter-spacing: 1px;
            text-transform: uppercase; color: {MUTED}; margin: 2px 0 -2px;
        }}

        /* ---------- Honeycomb category toggle buttons ----------
           Whole button is clickable. Active = primary (filled ink),
           inactive = secondary (outline). No checkmarks. */
        div[data-testid="stButton"] > button {{
            border-radius: 0 !important;
            clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
            height: 52px;
            font-weight: 700;
            font-size: 0.82rem;
            letter-spacing: 0.2px;
            box-shadow: none !important;
            transition: transform 0.1s ease, background 0.15s ease;
        }}
        div[data-testid="stButton"] > button:hover {{ transform: translateY(-1px); }}

        /* inactive (secondary) honeycomb */
        div[data-testid="stButton"] > button[kind="secondary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"] {{
            background: {PAPER} !important;
            color: {INK} !important;
            border: 1.5px solid {LINE} !important;
        }}
        /* active (primary) honeycomb */
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {{
            background: {INK} !important;
            color: {PAPER} !important;
            border: 1.5px solid {INK} !important;
        }}

        /* ---------- District selector & search → pill inputs ---------- */
        div[data-baseweb="select"] > div {{
            border-radius: 12px !important;
            border-color: {LINE} !important;
            background: #ffffff !important;
        }}
        div[data-testid="stTextInput"] input {{
            border-radius: 12px !important;
            border: 1px solid {LINE} !important;
            background: #ffffff !important;
            color: {INK} !important;
        }}

        /* ---------- Filters popover trigger ---------- */
        div[data-testid="stPopover"] > div > button {{
            border-radius: 12px !important;
            background: {INK} !important;
            color: {PAPER} !important;
            border: none !important;
            font-weight: 700 !important;
            height: 48px;
        }}

        /* ---------- Right-hand rating panel ---------- */
        @keyframes bpSlideIn {{
            from {{ transform: translateX(108%); }}
            to   {{ transform: translateX(0); }}
        }}
        .bp-panel {{
            position: fixed; top: 84px; right: 14px; z-index: 1200;
            width: 372px; max-width: 92vw; height: calc(100vh - 104px);
            background: {PAPER};
            border: 1px solid {LINE};
            border-radius: 18px;
            box-shadow: -14px 0 44px rgba(30,28,24,0.16);
            overflow: hidden;
            display: flex; flex-direction: column;
            animation: bpSlideIn 0.34s cubic-bezier(.22,.61,.36,1);
            font-family: "Source Sans Pro", system-ui, sans-serif;
        }}
        .bp-panel-head {{ padding: 22px 24px 18px; border-bottom: 1px solid {LINE}; }}
        .bp-tag {{
            display: inline-flex; align-items: center; gap: 7px;
            padding: 5px 11px; border-radius: 999px; font-size: 0.72rem;
            font-weight: 700; letter-spacing: 0.3px; text-transform: uppercase;
        }}
        .bp-tag i {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .bp-close {{
            float: right; width: 32px; height: 32px; border-radius: 10px;
            background: #F3EFE6; color: {MUTED}; text-decoration: none;
            display: flex; align-items: center; justify-content: center; font-size: 1.05rem;
        }}
        .bp-name {{ font-size: 1.5rem; font-weight: 800; letter-spacing: -0.6px; margin: 14px 0 4px; color: {INK}; line-height: 1.12; }}
        .bp-meta {{ font-size: 0.85rem; color: {MUTED}; font-weight: 600; }}
        .bp-score-row {{ padding: 20px 24px; border-bottom: 1px solid {LINE}; display: flex; align-items: center; gap: 14px; }}
        .bp-score {{ font-size: 2.6rem; font-weight: 800; letter-spacing: -1.5px; line-height: 1; color: {INK}; }}
        .bp-meter {{ font-size: 1rem; letter-spacing: 1px; }}
        .bp-meter .off {{ filter: grayscale(1); opacity: 0.3; }}
        .bp-count {{ font-size: 0.82rem; color: {MUTED}; font-weight: 600; margin-top: 5px; }}
        .bp-rate {{ padding: 22px 24px; flex: 1; }}
        .bp-rate-label {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: {MUTED}; margin-bottom: 6px; }}
        .bp-rate-help {{ font-size: 0.86rem; color: {MUTED}; margin-bottom: 16px; }}

        /* 5 clickable bees that fill on hover (row-reverse star-rating trick) */
        .bp-bees {{ display: flex; flex-direction: row-reverse; justify-content: flex-end; gap: 10px; }}
        .bp-bees a {{ font-size: 2rem; line-height: 1; text-decoration: none; filter: grayscale(1); opacity: 0.32;
                      transition: transform 0.1s ease, filter 0.15s, opacity 0.15s; }}
        .bp-bees a:hover, .bp-bees a:hover ~ a {{ filter: none; opacity: 1; transform: scale(1.08); }}
        .bp-bees a.set {{ filter: none; opacity: 1; }}
        .bp-success {{
            margin: 0 24px 22px; padding: 13px 16px; border-radius: 13px;
            background: #F0EDE2; border: 1px solid #E3DECF;
            font-size: 0.86rem; font-weight: 700; color: {INK_2};
        }}

        /* ---------- Overview / Top-rated panel (default right-hand state) ---------- */
        @keyframes bpFade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .bp-overview {{ animation: bpFade 0.25s ease; }}
        .bp-stats {{ display: flex; gap: 10px; padding: 18px 24px; border-bottom: 1px solid {LINE}; }}
        .bp-stat {{ flex: 1; background: #ffffff; border: 1px solid {LINE}; border-radius: 12px; padding: 10px 12px; }}
        .bp-stat-label {{ font-size: 0.64rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: {MUTED}; }}
        .bp-stat-value {{ font-size: 1.4rem; font-weight: 800; color: {INK}; margin-top: 3px; letter-spacing: -0.5px; line-height: 1; }}
        .bp-top {{ padding: 18px 24px; overflow-y: auto; flex: 1; }}
        .bp-top h4 {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; color: {MUTED}; margin: 0 0 12px; }}
        .bp-top-row {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 0; border-top: 1px solid {LINE}; }}
        .bp-top-row:first-of-type {{ border-top: 0; }}
        .bp-top-name {{ font-size: 0.95rem; font-weight: 700; color: {INK}; line-height: 1.2; }}
        .bp-top-meta {{ font-size: 0.78rem; color: {MUTED}; margin-top: 2px; }}
        .bp-top-score {{ font-size: 0.9rem; font-weight: 700; color: {INK}; white-space: nowrap; }}
        .bp-empty {{ padding: 40px 26px; text-align: center; color: {MUTED}; font-size: 0.9rem; line-height: 1.45; }}
        .bp-empty h4 {{ color: {INK}; font-size: 1.05rem; margin: 0 0 6px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. STATIC CONFIG
# ==============================================================================
CATEGORIES = [
    {"key": "cat_food", "short": "Food", "label": "Food & Drink", "parent": "Food & Drink",
     "subcategories": [
         {"key": "sub_rest", "label": "Restaurants", "values": ["Restaurants"]},
         {"key": "sub_cafe", "label": "Cafes", "values": ["Cafes"]},
         {"key": "sub_bake", "label": "Bakeries & Street Food", "values": ["Bakeries", "Markets"]},
     ]},
    {"key": "cat_nightlife", "short": "Night", "label": "Nightlife", "parent": "Nightlife",
     "subcategories": [
         {"key": "sub_bars", "label": "Bars & Pubs", "values": ["Bars"]},
         {"key": "sub_clubs", "label": "Clubs", "values": ["Clubs"]},
         {"key": "sub_brew", "label": "Breweries & Wine Bars", "values": ["Breweries & Wine Bars"]},
     ]},
    {"key": "cat_culture", "short": "Culture", "label": "Culture", "parent": "Culture & Heritage",
     "subcategories": [
         {"key": "sub_mus", "label": "Museums & Galleries", "values": ["Museums", "Galleries"]},
         {"key": "sub_land", "label": "Landmarks", "values": ["Landmark or Trail"]},
         {"key": "sub_church", "label": "Churches", "values": ["Churches"]},
     ]},
    {"key": "cat_nature", "short": "Nature", "label": "Nature", "parent": "Nature & Outdoors",
     "subcategories": [
         {"key": "sub_parks", "label": "Parks & Gardens", "values": ["Parks & Gardens"]},
         {"key": "sub_lakes", "label": "Lakes", "values": ["Lakes & Swimming"]},
         {"key": "sub_hike", "label": "Hiking & Trails", "values": ["Hiking & Bike Trails"]},
     ]},
    {"key": "cat_transport", "short": "Transit", "label": "Transport", "parent": "Public Transport",
     "subcategories": [], "is_transport": True},
]

DISTRICT_CENTERS = {
    "Mitte": {"coords": [52.5200, 13.4050], "zoom": 14},
    "Friedrichshain-Kreuzberg": {"coords": [52.5050, 13.4400], "zoom": 14},
    "Neukölln": {"coords": [52.4800, 13.4350], "zoom": 14},
    "Charlottenburg-Wilmersdorf": {"coords": [52.5000, 13.2800], "zoom": 14},
    "Pankow": {"coords": [52.5600, 13.4000], "zoom": 13},
    "Tempelhof-Schöneberg": {"coords": [52.4700, 13.3800], "zoom": 13},
}

DISTRICT_STEREOTYPES = {
    "Mitte": "Historically Berlin's core, Mitte is now the polished, corporate, and tourist center — high-end startup offices, government buildings, busy shopping streets, and chic cafes.",
    "Friedrichshain-Kreuzberg": "The alternative heart of Berlin. Famous for legendary techno clubs, punk heritage, colorful street art, and vibrant political activism.",
    "Neukölln": "Raw, edgy, and rapidly changing — diverse, multicultural, with international street food, smoky hipster bars, and the Tempelhofer Feld nearby.",
    "Charlottenburg-Wilmersdorf": "The elegant heart of old West Berlin: pre-war buildings, upscale dining, peaceful residential streets, and luxury shopping along Kurfürstendamm.",
    "Pankow": "Berlin's family-friendly haven (incl. Prenzlauer Berg): renovated apartments, organic markets, strollers, and relaxed cafes.",
    "Tempelhof-Schöneberg": "Leafy, historically the heart of Berlin's LGBTQ+ community: cozy local pubs, quiet streets, and the former Tempelhof Airport runway park.",
}


# ==============================================================================
# 3. HELPERS & DATA LOADERS
# ==============================================================================
def get_place_id(row):
    return "|".join([
        str(row.get("name", "Unknown place")),
        str(row.get("district_name", "Unknown district")),
        str(row.get("master_category", "")),
        str(row.get("subcategory", "")),
    ])


def get_rating_summary(ratings, place_id):
    place_ratings = ratings.get(place_id, [])
    if not place_ratings:
        return 0, 0
    return sum(place_ratings) / len(place_ratings), len(place_ratings)


def format_bees(rating):
    if rating <= 0:
        return "No bee ratings yet"
    full_bees = int(round(rating))
    return "🐝" * full_bees + "·" * (5 - full_bees)


def bee_meter_html(rating):
    active_bees = int(round(rating))
    bees = [
        f'<span class="{"" if bee_number <= active_bees else "off"}">🐝</span>'
        for bee_number in range(1, 6)
    ]
    return f'<span class="bp-meter">{"".join(bees)}</span>'


def rating_count_label(count):
    return f"{count} rating{'s' if count != 1 else ''}"


def hex_pin_icon(color, selected=False):
    """A honeycomb (hexagon) map marker in a muted category colour."""
    size = 34 if selected else 27
    h = round(size * 0.88)
    ring = (
        f"box-shadow:0 0 0 3px {ACCENT}, 0 3px 8px rgba(30,28,24,.4);"
        if selected else
        "box-shadow:0 2px 5px rgba(30,28,24,.35);"
    )
    dot = 9 if selected else 7
    html = (
        f'<div style="width:{size}px;height:{h}px;'
        f'clip-path:polygon(25% 0%,75% 0%,100% 50%,75% 100%,25% 100%,0% 50%);'
        f'background:{color};{ring}display:flex;align-items:center;justify-content:center;">'
        f'<div style="width:{dot}px;height:{dot}px;border-radius:50%;background:#fff;opacity:.92;"></div></div>'
    )
    return folium.DivIcon(html=html, icon_size=(size, h), icon_anchor=(size // 2, h // 2))


@st.cache_resource
def get_database_connection():
    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


@st.cache_data
def load_districts_layer():
    path = "data/layer_districts.geojson"
    if os.path.exists(path):
        return gpd.read_file(path)
    return None


con = get_database_connection()
districts_gdf = load_districts_layer()

# ==============================================================================
# 4. STATE INIT
# ==============================================================================
st.session_state.setdefault("selected_district", "City View (No Pins)")
st.session_state.setdefault("shuffle_seed", "beepov-default")
st.session_state.setdefault("clicked_place_id", None)
# Persisted map viewport — keeps the user's pan/zoom across reruns instead of
# snapping back to a default on every click.
st.session_state.setdefault("map_center", None)
st.session_state.setdefault("map_zoom", None)
for _cat in CATEGORIES:
    st.session_state.setdefault(_cat["key"], False)
# GEOLOCATION FEATURE START
st.session_state.setdefault("use_user_location", False)
st.session_state.setdefault("user_lat", None)
st.session_state.setdefault("user_lon", None)
st.session_state.setdefault("geo_widget_shown", False)
# GEOLOCATION FEATURE END

# Refine filters (live in the Filters popover)
st.session_state.setdefault("flt_free", False)
st.session_state.setdefault("flt_access", False)
st.session_state.setdefault("flt_vegan", False)
st.session_state.setdefault("flt_lgbtq", False)
st.session_state.setdefault("flt_max", 15)
st.session_state.setdefault("flt_minbee", 0)

district_list = (["City View (No Pins)"] + sorted(DISTRICT_CENTERS.keys())) if districts_gdf is not None else ["City View (No Pins)"]

# ==============================================================================
# 5. TOP BAR  (brand · district · search · location · honeycomb categories · filters)
# ==============================================================================
bar = st.columns([1.9, 1.5, 1.6, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8, 1.0], gap="small", vertical_alignment="center")

# --- Brand ---
with bar[0]:
    st.markdown(
        '<div class="bp-brand"><div class="bp-logo"><span></span><span></span></div>'
        '<div class="bp-word">bee<b>POV</b></div></div>',
        unsafe_allow_html=True,
    )

# --- District selector ---
with bar[1]:
    try:
        current_index = district_list.index(st.session_state["selected_district"])
    except ValueError:
        current_index = 0
    ui_selection = st.selectbox("District", options=district_list, index=current_index, label_visibility="collapsed")
    if ui_selection != st.session_state["selected_district"]:
        st.session_state["selected_district"] = ui_selection
        st.session_state["clicked_place_id"] = None
        st.session_state["use_user_location"] = False
        if ui_selection == "City View (No Pins)":
            st.session_state["map_center"], st.session_state["map_zoom"] = [52.5200, 13.4050], 11
        else:
            st.session_state["map_center"] = DISTRICT_CENTERS[ui_selection]["coords"]
            st.session_state["map_zoom"] = DISTRICT_CENTERS[ui_selection]["zoom"]
        st.rerun()

# --- Search (best-effort: jumps to a district when the name matches) ---
with bar[2]:
    search_value = st.text_input("Search", placeholder="Search a street, place or area", label_visibility="collapsed")
    if search_value:
        match = next((d for d in DISTRICT_CENTERS if search_value.strip().lower() in d.lower()), None)
        if match and match != st.session_state["selected_district"]:
            st.session_state["selected_district"] = match
            st.session_state["clicked_place_id"] = None
            st.session_state["use_user_location"] = False
            st.session_state["map_center"] = DISTRICT_CENTERS[match]["coords"]
            st.session_state["map_zoom"] = DISTRICT_CENTERS[match]["zoom"]
            st.rerun()

# --- Use my location (locate icon lives in the bar) ---
with bar[3]:
    # GEOLOCATION FEATURE START
    location = streamlit_geolocation()
    if location and location.get("latitude") is not None and location.get("longitude") is not None:
        lat, lon = location["latitude"], location["longitude"]
        # Only snap the map to the user when this is a new fix (a fresh click),
        # so the view stays put if they pan away afterwards.
        if lat != st.session_state.get("user_lat") or lon != st.session_state.get("user_lon"):
            st.session_state["user_lat"] = lat
            st.session_state["user_lon"] = lon
            st.session_state["use_user_location"] = True
            st.session_state["map_center"], st.session_state["map_zoom"] = [lat, lon], 15
            st.session_state["clicked_place_id"] = None
            st.rerun()
    # GEOLOCATION FEATURE END

# --- Honeycomb category toggles (whole button clickable, no checkmark) ---
for i, cat in enumerate(CATEGORIES):
    with bar[4 + i]:
        is_on = st.session_state.get(cat["key"], False)
        if st.button(cat["short"], key="tg_" + cat["key"], use_container_width=True,
                     type="primary" if is_on else "secondary"):
            st.session_state[cat["key"]] = not is_on
            st.rerun()

# --- Filters popover (refine + district vibe) ---
with bar[9]:
    with st.popover("Filters", use_container_width=True):
        sd = st.session_state["selected_district"]
        if sd != "City View (No Pins)":
            st.markdown(f"**{sd}**")
            st.caption(DISTRICT_STEREOTYPES.get(sd, ""))
            st.divider()

        all_on = all(st.session_state.get(c["key"], False) for c in CATEGORIES)
        if st.button("Clear all" if all_on else "Select all categories", use_container_width=True):
            for c in CATEGORIES:
                st.session_state[c["key"]] = not all_on
            st.rerun()

        st.markdown("**Refine results**")
        st.session_state["flt_free"] = st.checkbox("Free entry", value=st.session_state["flt_free"])
        st.session_state["flt_access"] = st.checkbox("Wheelchair accessible", value=st.session_state["flt_access"])
        st.session_state["flt_vegan"] = st.checkbox("Vegan friendly", value=st.session_state["flt_vegan"])
        st.session_state["flt_lgbtq"] = st.checkbox("LGBTQ+ friendly", value=st.session_state["flt_lgbtq"])
        st.session_state["flt_max"] = st.slider("Max places", 5, 50, st.session_state["flt_max"])
        st.session_state["flt_minbee"] = st.slider("Min 🐝 rating", 0, 5, st.session_state["flt_minbee"])

        if st.button("Shuffle results", use_container_width=True):
            st.session_state["shuffle_seed"] = datetime.utcnow().isoformat()

# --- Subcategory row (appears right under the bar when categories are toggled on) ---
visible_parents = [c for c in CATEGORIES if st.session_state.get(c["key"]) and not c.get("is_transport")]
if visible_parents:
    sub_cols = st.columns(len(visible_parents), gap="small")
    for col, cat in zip(sub_cols, visible_parents):
        with col:
            st.markdown(f'<div class="bp-subhead">{escape(cat["parent"])}</div>', unsafe_allow_html=True)
            for sub in cat["subcategories"]:
                st.checkbox(sub["label"],
                            value=st.session_state.get("flt_" + sub["key"], True),
                            key="flt_" + sub["key"])

# Resolve active selections from the honeycomb toggles -------------------------
selected_district = st.session_state["selected_district"]
active_subcategories = []
show_public_transport = False
parent_categories_selected = set()
for cat in CATEGORIES:
    if not st.session_state.get(cat["key"]):
        continue
    parent_categories_selected.add(cat["parent"])
    if cat.get("is_transport"):
        show_public_transport = True
    else:
        for sub in cat["subcategories"]:
            if st.session_state.get("flt_" + sub["key"], True):
                active_subcategories.extend(sub["values"])

apply_free = st.session_state["flt_free"]
apply_accessible = st.session_state["flt_access"]
apply_vegan = st.session_state["flt_vegan"]
apply_lgbtq = st.session_state["flt_lgbtq"]
max_results = st.session_state["flt_max"]
minimum_bee_rating = st.session_state["flt_minbee"]

# ==============================================================================
# 6. QUERY (DUCKDB)
# ==============================================================================
df_pins = None
if (selected_district != "City View (No Pins)"
        and (active_subcategories or show_public_transport)
        and os.path.exists("data/berlin_pois.parquet")):

    query = """
        SELECT name, district_name, master_category, subcategory, wkt_geometry, quality_score
        FROM 'data/berlin_pois.parquet'
        WHERE district_name = ?
        AND (
            (master_category = 'Nature & Outdoors' AND quality_score >= 1) OR
            (master_category != 'Nature & Outdoors' AND quality_score >= 2)
        )
    """
    params = [selected_district]
    category_conditions = []
    if active_subcategories:
        placeholders = ", ".join(["?"] * len(active_subcategories))
        category_conditions.append(f"subcategory IN ({placeholders})")
        params.extend(active_subcategories)
    if show_public_transport:
        category_conditions.append("master_category = 'Public Transport'")
    query += " AND (" + " OR ".join(category_conditions) + ")"
    if apply_free: query += " AND is_free = true"
    if apply_accessible: query += " AND is_accessible = true"
    if apply_vegan: query += " AND is_vegan_friendly = true"
    if apply_lgbtq: query += " AND is_lgbtq = true"
    query += " ORDER BY hash(coalesce(name, '') || ?) LIMIT 200"
    params.append(st.session_state["shuffle_seed"])

    df_all = con.execute(query, params).df()
    if len(active_subcategories) > 1 and not df_all.empty:
        per_cat = max(1, max_results // len(active_subcategories))
        df_pins = pd.concat([grp.head(per_cat) for _, grp in df_all.groupby("subcategory")]).reset_index(drop=True)
    else:
        df_pins = df_all.head(max_results).copy()

bee_ratings = load_bee_ratings()
if df_pins is not None and not df_pins.empty:
    df_pins["place_id"] = df_pins.apply(get_place_id, axis=1)
    summaries = df_pins["place_id"].apply(lambda pid: get_rating_summary(bee_ratings, pid))
    df_pins["bee_average"] = summaries.apply(lambda s: s[0])
    df_pins["bee_count"] = summaries.apply(lambda s: s[1])
    if minimum_bee_rating > 0:
        df_pins = df_pins[(df_pins["bee_count"] > 0) & (df_pins["bee_average"] >= minimum_bee_rating)]

# ==============================================================================
# 7. MAP
# ==============================================================================
# Use the persisted viewport (set by navigation actions / preserved across clicks).
# Fall back to a sensible default only on first load.
map_center = st.session_state.get("map_center")
map_zoom = st.session_state.get("map_zoom")
if not map_center or map_zoom is None:
    if selected_district == "City View (No Pins)":
        map_center, map_zoom = [52.5200, 13.4050], 11
    else:
        map_center = DISTRICT_CENTERS[selected_district]["coords"]
        map_zoom = DISTRICT_CENTERS[selected_district]["zoom"]
    st.session_state["map_center"], st.session_state["map_zoom"] = map_center, map_zoom

m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="CartoDB positron", zoom_control=True)

if districts_gdf is not None:
    def get_district_style(feature):
        d_name = feature["properties"].get("Gemeinde_name", feature["properties"].get("name", ""))
        if selected_district != "City View (No Pins)" and d_name == selected_district:
            return {"fillColor": ACCENT, "color": INK, "fillOpacity": 0.10, "weight": 2}
        return {"fillColor": "#d9d4c8", "color": "#c4bdaf", "fillOpacity": 0.04, "weight": 1}

    folium.GeoJson(districts_gdf, style_function=get_district_style).add_to(m)

marker_cluster = MarkerCluster().add_to(m)
if df_pins is not None and not df_pins.empty:
    for _, row in df_pins.iterrows():
        try:
            point = shapely.wkt.loads(row["wkt_geometry"])
            if point.geom_type != "Point":
                point = point.centroid
        except Exception:
            continue
        color = CATEGORY_COLORS.get(row.get("master_category", ""), MUTED)
        is_selected = st.session_state.get("clicked_place_id") == row["place_id"]
        folium.Marker(
            location=[point.y, point.x],
            icon=hex_pin_icon(color, selected=is_selected),
            tooltip=str(row["name"]),
        ).add_to(marker_cluster)

# GEOLOCATION FEATURE START
if (st.session_state["use_user_location"]
        and st.session_state["user_lat"] is not None
        and st.session_state["user_lon"] is not None):
    folium.Marker(
        location=[st.session_state["user_lat"], st.session_state["user_lon"]],
        tooltip="You are here",
        icon=folium.Icon(color="black", icon="user"),
    ).add_to(m)
# GEOLOCATION FEATURE END

map_data = st_folium(m, use_container_width=True, height=760,
                     returned_objects=["last_active_drawing", "last_object_clicked", "center", "zoom"])

# ---- Click handling ----------------------------------------------------------
if map_data:
    # Persist the user's current pan/zoom so the next rerun keeps their view.
    if map_data.get("center"):
        st.session_state["map_center"] = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom") is not None:
        st.session_state["map_zoom"] = map_data["zoom"]

    # District click → select it but keep the user's current map scope (no recenter)
    if map_data.get("last_active_drawing"):
        props = map_data["last_active_drawing"].get("properties", {})
        clicked_district = props.get("Gemeinde_name", props.get("name", ""))
        if clicked_district in DISTRICT_CENTERS and st.session_state["selected_district"] != clicked_district:
            st.session_state["selected_district"] = clicked_district
            st.session_state["clicked_place_id"] = None
            st.rerun()

    # Marker click → open the right-hand rating panel
    if map_data.get("last_object_clicked") and df_pins is not None and not df_pins.empty:
        clat = map_data["last_object_clicked"]["lat"]
        clng = map_data["last_object_clicked"]["lng"]
        matched = None
        for _, row in df_pins.iterrows():
            try:
                pt = shapely.wkt.loads(row["wkt_geometry"])
                if pt.geom_type != "Point":
                    pt = pt.centroid
                if abs(pt.y - clat) < 1e-5 and abs(pt.x - clng) < 1e-5:
                    matched = row["place_id"]
                    break
            except Exception:
                continue
        if matched and st.session_state.get("clicked_place_id") != matched:
            st.session_state["clicked_place_id"] = matched
            st.rerun()

# ==============================================================================
# 8. RIGHT-HAND RATING PANEL  (visible only when a datapoint is clicked)
# ==============================================================================
clicked_id = st.session_state.get("clicked_place_id")
clicked_row = None
if clicked_id and df_pins is not None and not df_pins.empty:
    hit = df_pins[df_pins["place_id"] == clicked_id]
    if not hit.empty:
        clicked_row = hit.iloc[0]

if clicked_row is not None:
    cat = clicked_row.get("master_category", "")
    color = CATEGORY_COLORS.get(cat, MUTED)
    avg = float(clicked_row.get("bee_average", 0))
    count = int(clicked_row.get("bee_count", 0))
    rounded = int(round(avg))
    meter = "".join(
        f'<span class="{"" if (count and i <= rounded) else "off"}">🐝</span>' for i in range(1, 6)
    )
    score_text = f"{avg:.1f}" if count else "–"
    count_text = f"{count} bee rating{'s' if count != 1 else ''}" if count else "No ratings yet"

    enc = urllib.parse.quote(clicked_id)
    # bees rendered 5→1 so the row-reverse CSS hover fills 1..N left-to-right
    bees = "".join(
        f'<a href="?rate={n}&place_id={enc}" target="_self" title="{n} bees">🐝</a>'
        for n in range(5, 0, -1)
    )
    success = ""
    if "bee_rating_success" in st.session_state:
        success = f'<div class="bp-success">🐝 &nbsp;{escape(st.session_state.pop("bee_rating_success"))}</div>'

    st.markdown(
        f"""
        <div class="bp-panel">
            <div class="bp-panel-head">
                <a class="bp-close" href="?close_panel=1" target="_self">✕</a>
                <span class="bp-tag" style="background:{color}1f;color:{color};"><i style="background:{color};"></i>{escape(str(cat))}</span>
                <div class="bp-name">{escape(str(clicked_row['name']))}</div>
                <div class="bp-meta">{escape(str(clicked_row.get('district_name','')))} · Berlin</div>
            </div>
            <div class="bp-score-row">
                <div class="bp-score">{score_text}</div>
                <div>
                    <div class="bp-meter">{meter}</div>
                    <div class="bp-count">{count_text}</div>
                </div>
            </div>
            <div class="bp-rate">
                <div class="bp-rate-label">Your rating</div>
                <div class="bp-rate-help">Tap a bee to score this place from 1 to 5.</div>
                <div class="bp-bees">{bees}</div>
            </div>
            {success}
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------------------
# Default right-hand state: district Overview + Top Bee-rated places.
# Shown ONLY when there are points loaded on the map — not just on district select.
# ------------------------------------------------------------------------------
elif (selected_district != "City View (No Pins)"
        and df_pins is not None and not df_pins.empty):
    success = ""
    if "bee_rating_success" in st.session_state:
        success = f'<div class="bp-success">🐝 &nbsp;{escape(st.session_state.pop("bee_rating_success"))}</div>'

    visible_count = len(df_pins)
    rated_count = int((df_pins["bee_count"] > 0).sum())
    total_ratings = int(df_pins["bee_count"].sum())
    view_average = (
        (df_pins["bee_average"] * df_pins["bee_count"]).sum() / total_ratings
    ) if total_ratings else 0

    rated_places = df_pins[df_pins["bee_count"] > 0].sort_values(
        ["bee_average", "bee_count"], ascending=False
    ).head(5)
    if not rated_places.empty:
        top_rows = "".join(
            f"""
            <div class="bp-top-row">
                <div>
                    <div class="bp-top-name">{escape(str(r['name']))}</div>
                    <div class="bp-top-meta">{escape(str(r['subcategory']))} · {rating_count_label(int(r['bee_count']))}</div>
                </div>
                <div style="text-align:right;">
                    {bee_meter_html(r['bee_average'])}
                    <div class="bp-top-score">{r['bee_average']:.1f}/5</div>
                </div>
            </div>
            """
            for _, r in rated_places.iterrows()
        )
        top_section = f'<div class="bp-top"><h4>Top bee-rated places</h4>{top_rows}</div>'
    else:
        top_section = (
            '<div class="bp-empty">No bee ratings here yet.<br>'
            'Click a pin on the map to rate a place.</div>'
        )

    st.markdown(
        f"""
        <div class="bp-panel bp-overview">
            <div class="bp-panel-head">
                <div class="bp-name">{escape(selected_district)}</div>
                <div class="bp-meta">Overview · Berlin</div>
            </div>
            <div class="bp-stats">
                <div class="bp-stat"><div class="bp-stat-label">Visible</div><div class="bp-stat-value">{visible_count}</div></div>
                <div class="bp-stat"><div class="bp-stat-label">Rated</div><div class="bp-stat-value">{rated_count}</div></div>
                <div class="bp-stat"><div class="bp-stat-label">Average</div><div class="bp-stat-value">{view_average:.1f}</div></div>
            </div>
            {top_section}
            {success}
        </div>
        """,
        unsafe_allow_html=True,
    )
