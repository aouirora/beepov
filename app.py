import os
import json
from functools import partial
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
# DESIGN TOKENS  (charcoal + muted amber — Karina's scheme)
# ==============================================================================
INK      = "#23211D"
INK_2    = "#3A372F"
PAPER    = "#FAF8F3"
LINE     = "#E7E2D7"
MUTED    = "#8C8578"
ACCENT   = "#B5863C"
ACCENT_D = "#936B2C"

CATEGORY_COLORS = {
    "Food & Drink":       "#B07C3A",
    "Nightlife":          "#7E6597",
    "Culture & Heritage": "#5878A0",
    "Nature & Outdoors":  "#6B8F5E",
    "Public Transport":   "#8C8578",
}

# ==============================================================================
# 0. RATINGS UTILITIES & QUERY PARAM HANDLER
# ==============================================================================
RATINGS_PATH = "data/bee_ratings.json"

@st.cache_data
def load_bee_ratings():
    if not os.path.exists(RATINGS_PATH):
        return {}
    try:
        with open(RATINGS_PATH, "r", encoding="utf-8") as f:
            ratings = json.load(f)
            return {k: [int(v) for v in vs] for k, vs in ratings.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}

def save_bee_rating(place_id, rating):
    ratings = load_bee_ratings()
    ratings.setdefault(place_id, []).append(int(rating))
    os.makedirs(os.path.dirname(RATINGS_PATH), exist_ok=True)
    with open(RATINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(ratings, f, indent=2, ensure_ascii=False)
    load_bee_ratings.clear()

# Rating submitted from the panel bee-links — keep panel open on the rated place
if "rate" in st.query_params and "place_id" in st.query_params:
    try:
        rate_val = int(st.query_params["rate"])
        place_id_val = st.query_params["place_id"]
        save_bee_rating(place_id_val, rate_val)
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
    initial_sidebar_state="collapsed",
)

st.markdown(
    f"""
    <style>
        /* ---------- Layout: trim chrome so the map fills the screen ---------- */
        .block-container {{ padding: 0.55rem 0.9rem 0 0.9rem; max-width: 100%; }}
        header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
        #MainMenu, footer {{ visibility: hidden; }}
        section[data-testid="stSidebar"] {{ display: none; }}
        div[data-testid="stToolbar"] {{ display: none; }}
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

        /* ---------- Subcategory row ---------- */
        .bp-subhead {{
            font-size: 0.7rem; font-weight: 700; letter-spacing: 1px;
            text-transform: uppercase; color: {MUTED}; margin: 2px 0 -2px;
        }}

        /* ---------- Honeycomb category toggle buttons ---------- */
        div[data-testid="stButton"] > button {{
            border-radius: 0 !important;
            clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
            height: 52px; font-weight: 700; font-size: 0.82rem; letter-spacing: 0.2px;
            box-shadow: none !important;
            transition: transform 0.1s ease, background 0.15s ease;
        }}
        div[data-testid="stButton"] > button:hover {{ transform: translateY(-1px); }}
        div[data-testid="stButton"] > button[kind="secondary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"] {{
            background: {PAPER} !important; color: {INK} !important; border: 1.5px solid {LINE} !important;
        }}
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {{
            background: {INK} !important; color: {PAPER} !important; border: 1.5px solid {INK} !important;
        }}

        /* ---------- Close panel button (native st.button, repositioned via CSS) ---------- */
        .st-key-bp_close button {{
            position: fixed !important; top: 93px !important; right: 22px !important;
            z-index: 1300 !important; width: 32px !important; height: 32px !important;
            min-width: 32px !important; border-radius: 10px !important; clip-path: none !important;
            background: #F3EFE6 !important; color: {MUTED} !important;
            border: none !important; padding: 0 !important; font-size: 1.05rem !important;
            transform: none !important; font-weight: normal !important; letter-spacing: 0 !important;
        }}
        .st-key-bp_close button:hover {{ background: {LINE} !important; transform: none !important; }}

        /* ---------- Inputs ---------- */
        div[data-baseweb="select"] > div {{
            border-radius: 12px !important; border-color: {LINE} !important; background: #ffffff !important;
        }}
        div[data-testid="stTextInput"] input {{
            border-radius: 12px !important; border: 1px solid {LINE} !important;
            background: #ffffff !important; color: {INK} !important;
        }}

        /* ---------- Filters popover trigger ---------- */
        div[data-testid="stPopover"] > div > button {{
            border-radius: 12px !important; background: {INK} !important; color: {PAPER} !important;
            border: none !important; font-weight: 700 !important; height: 48px;
        }}

        /* ---------- Sliding detail panel ---------- */
        @keyframes bpSlideIn {{ from {{ transform: translateX(108%); }} to {{ transform: translateX(0); }} }}
        .bp-panel {{
            position: fixed; top: 84px; right: 14px; z-index: 1200;
            width: 372px; max-width: 92vw; height: calc(100vh - 104px);
            background: {PAPER}; border: 1px solid {LINE}; border-radius: 18px;
            box-shadow: -14px 0 44px rgba(30,28,24,0.16);
            overflow: hidden; display: flex; flex-direction: column;
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
        .bp-bees {{ display: flex; flex-direction: row-reverse; justify-content: flex-end; gap: 10px; }}
        .bp-bees a {{ font-size: 2rem; line-height: 1; text-decoration: none; filter: grayscale(1); opacity: 0.32;
                      transition: transform 0.1s ease, filter 0.15s, opacity 0.15s; }}
        .bp-bees a:hover, .bp-bees a:hover ~ a {{ filter: none; opacity: 1; transform: scale(1.08); }}
        .bp-success {{
            margin: 0 24px 22px; padding: 13px 16px; border-radius: 13px;
            background: #F0EDE2; border: 1px solid #E3DECF;
            font-size: 0.86rem; font-weight: 700; color: {INK_2};
        }}

        /* ---------- Overview / Top-rated panel ---------- */
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
        .bp-desc {{ font-size: 0.86rem; color: {MUTED}; line-height: 1.45; margin-top: 9px; }}

        /* ---------- Floating legend + contextual CTA chips ---------- */
        .bee-float-legend {{
            position: fixed; bottom: 22px; left: 22px; z-index: 1100;
            background: rgba(255,253,248,0.96); border: 1px solid {LINE};
            border-radius: 14px; padding: 10px 14px;
            box-shadow: 0 6px 22px rgba(30,28,24,0.14);
            font-size: 0.78rem; color: {MUTED};
        }}
        .bee-float-legend .count {{ font-weight: 800; color: {INK}; font-size: 0.92rem; margin-bottom: 7px; }}
        .bee-float-legend .row {{ display: flex; flex-wrap: wrap; gap: 7px 12px; max-width: 250px; }}
        .bee-float-legend .item {{ display: inline-flex; align-items: center; gap: 5px; }}
        .bee-float-legend .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
        .bee-float-cta {{
            position: fixed; top: 96px; left: 46%; transform: translateX(-50%); z-index: 1100;
            background: {INK}; color: {PAPER}; border-radius: 999px;
            padding: 10px 22px; font-size: 0.9rem; font-weight: 600;
            box-shadow: 0 8px 26px rgba(30,28,24,0.28);
        }}
        .bee-float-cta b {{ color: {ACCENT}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. CONSTANTS
# ==============================================================================
CATEGORIES = [
    {"key": "cat_food", "short": "Food", "label": "Food & Drink", "parent": "Food & Drink",
     "subcategories": [
         {"key": "sub_rest", "label": "Restaurants",          "values": ["Restaurants"]},
         {"key": "sub_cafe", "label": "Cafes",                "values": ["Cafes"]},
         {"key": "sub_bake", "label": "Bakeries & Street Food","values": ["Bakeries", "Markets"]},
     ]},
    {"key": "cat_nightlife", "short": "Night", "label": "Nightlife", "parent": "Nightlife",
     "subcategories": [
         {"key": "sub_bars",  "label": "Bars & Pubs",             "values": ["Bars"]},
         {"key": "sub_clubs", "label": "Clubs",                   "values": ["Clubs"]},
         {"key": "sub_brew",  "label": "Breweries & Wine Bars",   "values": ["Breweries & Wine Bars"]},
     ]},
    {"key": "cat_culture", "short": "Culture", "label": "Culture", "parent": "Culture & Heritage",
     "subcategories": [
         {"key": "sub_mus",    "label": "Museums & Galleries", "values": ["Museums", "Galleries"]},
         {"key": "sub_land",   "label": "Landmarks",           "values": ["Landmark or Trail"]},
         {"key": "sub_church", "label": "Churches",            "values": ["Churches"]},
     ]},
    {"key": "cat_nature", "short": "Nature", "label": "Nature", "parent": "Nature & Outdoors",
     "subcategories": [
         {"key": "sub_parks", "label": "Parks & Gardens",  "values": ["Parks & Gardens"]},
         {"key": "sub_lakes", "label": "Lakes",            "values": ["Lakes & Swimming"]},
         {"key": "sub_hike",  "label": "Hiking & Trails", "values": ["Hiking & Bike Trails"]},
     ]},
    {"key": "cat_transport", "short": "Transit", "label": "Transport", "parent": "Public Transport",
     "subcategories": [], "is_transport": True},
]

DISTRICT_CENTERS = {
    "Mitte":                      {"coords": [52.5200, 13.4050], "zoom": 14},
    "Friedrichshain-Kreuzberg":   {"coords": [52.5050, 13.4400], "zoom": 14},
    "Neukölln":                   {"coords": [52.4800, 13.4350], "zoom": 14},
    "Charlottenburg-Wilmersdorf": {"coords": [52.5000, 13.2800], "zoom": 14},
    "Pankow":                     {"coords": [52.5600, 13.4000], "zoom": 13},
    "Tempelhof-Schöneberg":       {"coords": [52.4700, 13.3800], "zoom": 13},
    "Lichtenberg":                {"coords": [52.5349, 13.5098], "zoom": 13},
    "Marzahn-Hellersdorf":        {"coords": [52.5211, 13.5788], "zoom": 13},
    "Reinickendorf":              {"coords": [52.5957, 13.2913], "zoom": 13},
    "Spandau":                    {"coords": [52.5258, 13.1788], "zoom": 13},
    "Steglitz-Zehlendorf":        {"coords": [52.4348, 13.2391], "zoom": 13},
    "Treptow-Köpenick":           {"coords": [52.4296, 13.6112], "zoom": 13},
}

DISTRICT_STEREOTYPES = {
    "Mitte": "Historically Berlin's core, Mitte is now the polished, corporate, and tourist center. It is characterized by high-end startup offices, government buildings, busy shopping districts, and chic cafes.",
    "Friedrichshain-Kreuzberg": "The alternative heart of Berlin. Famous for its legendary techno clubs, punk heritage, colorful street art, and vibrant political activism.",
    "Neukölln": "Raw, edgy, and rapidly changing. Neukölln is famous for its diverse, multicultural atmosphere, international street food, smoky hipster bars, and proximity to the Tempelhofer Feld.",
    "Charlottenburg-Wilmersdorf": "The wealthy, elegant heart of old West Berlin. It is known for its beautiful pre-war buildings, upscale dining, peaceful residential areas, and luxury shopping along Kurfürstendamm.",
    "Pankow": "Berlin's family-friendly haven (including Prenzlauer Berg). Popularly stereotyped as a cozy neighborhood of renovated apartments, organic food markets, baby strollers, and relaxed cafes.",
    "Tempelhof-Schöneberg": "A leafy district that is historically the heart of Berlin's LGBTQ+ community. It features cozy local pubs, quiet residential areas, and borders the massive former Tempelhof Airport runway park.",
    "Lichtenberg": "Working-class East Berlin with a socialist backbone. Known for the Stasi Museum, sprawling prefab housing estates, an authentic Vietnamese community around the Dong Xuan Center, and growing spillover from Friedrichshain.",
    "Marzahn-Hellersdorf": "Berlin's GDR panel-block heartland — quiet, affordable, and underrated. Home to the spectacular Gardens of the World and a tight-knit community of long-term residents far from tourist circuits.",
    "Reinickendorf": "A calm, leafy northern district bordering Tegel forest and lake. Mostly residential with little tourist footfall — a genuine neighborhood far from the city buzz, popular with families and outdoor lovers.",
    "Spandau": "Berlin's westernmost district, almost a city unto itself. Known for its well-preserved medieval old town, the imposing Spandau Citadel, and a slower pace of life that feels worlds away from central Berlin.",
    "Steglitz-Zehlendorf": "A prosperous, leafy southwestern district of villas, lakes, and forests. Home to the Dahlem museums, the Free University, and Wannsee — more suburban retreat than urban buzz.",
    "Treptow-Köpenick": "Berlin's most nature-rich district, where forests, rivers, and lakes dominate. Known for Müggelsee, Köpenick's charming old town, and Treptower Park with its monumental Soviet war memorial.",
}

# ==============================================================================
# 3. HELPERS & DATA LOADERS
# ==============================================================================
def get_place_id(row):
    return str(row["id"])

def get_rating_summary(ratings, place_id):
    place_ratings = ratings.get(place_id, [])
    if not place_ratings:
        return 0, 0
    return sum(place_ratings) / len(place_ratings), len(place_ratings)

def format_bees(rating):
    if rating <= 0:
        return "No Bee ratings yet"
    full_bees = int(round(rating))
    return "🐝" * full_bees + "·" * (5 - full_bees)

def bee_meter_html(rating):
    active_bees = int(round(rating))
    bees = [
        f'<span class="{"" if i <= active_bees else "off"}">🐝</span>'
        for i in range(1, 6)
    ]
    return f'<span class="bp-meter">{"".join(bees)}</span>'

def rating_count_label(count):
    return f"{count} rating{'s' if count != 1 else ''}"

def hex_pin_icon(color, selected=False):
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

def _district_style(selected_district, feature):
    """Module-level so it can be pickled by st.cache_data."""
    d_name = feature["properties"].get("Gemeinde_name",
              feature["properties"].get("name", ""))
    if selected_district != "City View (No Pins)" and d_name == selected_district:
        return {"fillColor": ACCENT, "color": INK, "fillOpacity": 0.10, "weight": 2}
    return {"fillColor": "#d9d4c8", "color": "#c4bdaf", "fillOpacity": 0.04, "weight": 1}


@st.cache_data(show_spinner=False)
def _build_folium_map(map_center_t, map_zoom, selected_district, pins_hash, geo_point,
                      _districts_gdf, _df_pins):
    """Build the folium map and cache it by content.

    clicked_place_id is intentionally excluded from the cache key so that
    clicking a pin returns the exact same pickled object → identical HTML bytes
    → st_folium detects no change → Leaflet is NOT recreated → no map flash.
    """
    _m = folium.Map(location=list(map_center_t), zoom_start=map_zoom,
                    tiles="CartoDB positron", zoom_control=True)

    if _districts_gdf is not None:
        folium.GeoJson(
            _districts_gdf,
            style_function=partial(_district_style, selected_district),
        ).add_to(_m)

    if _df_pins is not None and not _df_pins.empty:
        for _, row in _df_pins.iterrows():
            try:
                pt = shapely.wkt.loads(row["wkt_geometry"])
                if pt.geom_type != "Point":
                    pt = pt.centroid
            except Exception:
                continue
            _color = CATEGORY_COLORS.get(row.get("master_category", ""), MUTED)
            folium.Marker(
                location=[pt.y, pt.x],
                icon=hex_pin_icon(_color, selected=False),
                tooltip=escape(str(row["name"])),
            ).add_to(_m)

    if geo_point:
        folium.Marker(
            location=list(geo_point),
            tooltip="You are here",
            icon=folium.Icon(color="black", icon="user"),
        ).add_to(_m)

    return _m

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

with st.spinner("Loading Berlin map data…"):
    con = get_database_connection()
    districts_gdf = load_districts_layer()

# ==============================================================================
# 4. STATE INIT
# ==============================================================================
st.session_state.setdefault("selected_district", "City View (No Pins)")
st.session_state.setdefault("shuffle_seed", "beepov-default")
st.session_state.setdefault("clicked_place_id", None)
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
st.session_state.setdefault("flt_free",   False)
st.session_state.setdefault("flt_access", False)
st.session_state.setdefault("flt_vegan",  False)
st.session_state.setdefault("flt_lgbtq",  False)
st.session_state.setdefault("flt_max",    15)
st.session_state.setdefault("flt_minbee", 0)

district_list = ["City View (No Pins)"] + sorted(DISTRICT_CENTERS.keys())

# ==============================================================================
# 5. TOP BAR  (brand · district · search · location · honeycomb categories · filters)
# ==============================================================================
bar = st.columns([1.9, 1.5, 1.6, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8, 1.0], gap="small", vertical_alignment="center")

with bar[0]:
    st.markdown(
        '<div class="bp-brand"><div class="bp-logo"><span></span><span></span></div>'
        '<div class="bp-word">bee<b>POV</b></div></div>',
        unsafe_allow_html=True,
    )

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
            st.session_state["map_center"] = [52.5200, 13.4050]
            st.session_state["map_zoom"]   = 11
        else:
            st.session_state["map_center"] = DISTRICT_CENTERS[ui_selection]["coords"]
            st.session_state["map_zoom"]   = DISTRICT_CENTERS[ui_selection]["zoom"]
        st.rerun()

with bar[2]:
    search_value = st.text_input("Search", placeholder="Search a district", label_visibility="collapsed")
    if search_value:
        match = next((d for d in DISTRICT_CENTERS if search_value.strip().lower() in d.lower()), None)
        if match and match != st.session_state["selected_district"]:
            st.session_state["selected_district"] = match
            st.session_state["clicked_place_id"] = None
            st.session_state["use_user_location"] = False
            st.session_state["map_center"] = DISTRICT_CENTERS[match]["coords"]
            st.session_state["map_zoom"]   = DISTRICT_CENTERS[match]["zoom"]
            st.rerun()

# GEOLOCATION FEATURE START
with bar[3]:
    location = streamlit_geolocation()
    if location and location.get("latitude") is not None and location.get("longitude") is not None:
        lat, lon = location["latitude"], location["longitude"]
        if lat != st.session_state.get("user_lat") or lon != st.session_state.get("user_lon"):
            st.session_state["user_lat"] = lat
            st.session_state["user_lon"] = lon
            st.session_state["use_user_location"] = True
            st.session_state["map_center"] = [lat, lon]
            st.session_state["map_zoom"]   = 15
            st.session_state["clicked_place_id"] = None
            st.rerun()
# GEOLOCATION FEATURE END

for i, cat in enumerate(CATEGORIES):
    with bar[4 + i]:
        is_on = st.session_state.get(cat["key"], False)
        if st.button(cat["short"], key="tg_" + cat["key"], use_container_width=True,
                     type="primary" if is_on else "secondary"):
            st.session_state[cat["key"]] = not is_on
            st.rerun()

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
        st.session_state["flt_free"]   = st.checkbox("Free entry",            value=st.session_state["flt_free"])
        st.session_state["flt_access"] = st.checkbox("Wheelchair accessible", value=st.session_state["flt_access"])
        st.session_state["flt_vegan"]  = st.checkbox("Vegan friendly",        value=st.session_state["flt_vegan"])
        st.session_state["flt_lgbtq"]  = st.checkbox("LGBTQ+ friendly",       value=st.session_state["flt_lgbtq"])
        st.session_state["flt_max"]    = st.slider("Max places", 5, 50, st.session_state["flt_max"])
        st.session_state["flt_minbee"] = st.slider("Min 🐝 rating", 0, 5, st.session_state["flt_minbee"])
        if st.button("Shuffle results", use_container_width=True):
            st.session_state["shuffle_seed"] = datetime.utcnow().isoformat()

# Subcategory row (appears under the bar when a category is toggled on)
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

# Resolve active selections from honeycomb toggles
selected_district    = st.session_state["selected_district"]
active_subcategories = []
show_public_transport = False
for cat in CATEGORIES:
    if not st.session_state.get(cat["key"]):
        continue
    if cat.get("is_transport"):
        show_public_transport = True
    else:
        for sub in cat["subcategories"]:
            if st.session_state.get("flt_" + sub["key"], True):
                active_subcategories.extend(sub["values"])

apply_free        = st.session_state["flt_free"]
apply_accessible  = st.session_state["flt_access"]
apply_vegan       = st.session_state["flt_vegan"]
apply_lgbtq       = st.session_state["flt_lgbtq"]
max_results       = st.session_state["flt_max"]
minimum_bee_rating = st.session_state["flt_minbee"]

# ==============================================================================
# 6. QUERY (DUCKDB)  — logic unchanged from main
# ==============================================================================
df_pins = None
if (selected_district != "City View (No Pins)"
        and (active_subcategories or show_public_transport)
        and os.path.exists("data/berlin_pois.parquet")):

    query = """
        SELECT id, name, district_name, master_category, subcategory, wkt_geometry, quality_score
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
    if apply_free:       query += " AND is_free = true"
    if apply_accessible: query += " AND is_accessible = true"
    if apply_vegan:      query += " AND is_vegan_friendly = true"
    if apply_lgbtq:      query += " AND is_lgbtq = true"
    query += " ORDER BY hash(coalesce(name, '') || ?) LIMIT 200"
    params.append(st.session_state["shuffle_seed"])

    with st.spinner("Finding places…"):
        df_all = con.execute(query, params).df()
    if df_all is None:
        df_all = pd.DataFrame()

    if len(active_subcategories) > 1 and not df_all.empty:
        per_cat = max(1, max_results // len(active_subcategories))
        df_pins = pd.concat([grp.head(per_cat) for _, grp in df_all.groupby("subcategory")]).reset_index(drop=True)
    else:
        df_pins = df_all.head(max_results).copy()

bee_ratings = load_bee_ratings()
if df_pins is not None and not df_pins.empty:
    df_pins["place_id"] = df_pins.apply(get_place_id, axis=1)
    rating_summaries = df_pins["place_id"].apply(lambda pid: get_rating_summary(bee_ratings, pid))
    df_pins["bee_average"] = rating_summaries.apply(lambda s: s[0])
    df_pins["bee_count"]   = rating_summaries.apply(lambda s: s[1])
    if minimum_bee_rating > 0:
        df_pins = df_pins[(df_pins["bee_count"] > 0) & (df_pins["bee_average"] >= minimum_bee_rating)]

# ==============================================================================
# 7. MAP
# ==============================================================================
# Use the persisted viewport so pan/zoom survive reruns; fall back to district
# centre only on first load or when the district changes.
map_center = st.session_state.get("map_center")
map_zoom   = st.session_state.get("map_zoom")
if not map_center or map_zoom is None:
    # GEOLOCATION FEATURE START
    if st.session_state["use_user_location"] and st.session_state["user_lat"] is not None:
        map_center = [st.session_state["user_lat"], st.session_state["user_lon"]]
        map_zoom   = 15
    # GEOLOCATION FEATURE END
    elif selected_district == "City View (No Pins)":
        map_center, map_zoom = [52.5200, 13.4050], 11
    else:
        map_center = DISTRICT_CENTERS[selected_district]["coords"]
        map_zoom   = DISTRICT_CENTERS[selected_district]["zoom"]
    st.session_state["map_center"] = map_center
    st.session_state["map_zoom"]   = map_zoom

# Stable hash of pin content — excludes clicked_place_id so clicks hit the cache
_pins_hash = ""
if df_pins is not None and not df_pins.empty:
    _pins_hash = "|".join(df_pins["place_id"].astype(str).sort_values().tolist())

_geo_point = None
# GEOLOCATION FEATURE START
if st.session_state["use_user_location"] and st.session_state["user_lat"] is not None:
    _geo_point = (st.session_state["user_lat"], st.session_state["user_lon"])
# GEOLOCATION FEATURE END

m = _build_folium_map(
    tuple(map_center), map_zoom, selected_district, _pins_hash, _geo_point,
    districts_gdf, df_pins,
)

clicked_id = st.session_state.get("clicked_place_id")

# Key changes with district so the component remounts (recenters) only on district
# switch; within the same district the iframe keeps whatever pan/zoom the user set.
import re as _re
_map_key = "map_" + _re.sub(r"[^a-z0-9]", "_", selected_district.lower())
if st.session_state.get("use_user_location"):
    _map_key += "_geo"

map_data = st_folium(
    m,
    key=_map_key,
    use_container_width=True,
    height=760,
    returned_objects=["last_active_drawing", "last_object_clicked"],
)

# Click handling
if map_data:
    # District click → change district (full rerun needed to re-query)
    if map_data.get("last_active_drawing"):
        props = map_data["last_active_drawing"].get("properties", {})
        clicked_district = props.get("Gemeinde_name", props.get("name", ""))
        if clicked_district in DISTRICT_CENTERS and st.session_state["selected_district"] != clicked_district:
            st.session_state["selected_district"] = clicked_district
            st.session_state["clicked_place_id"] = None
            st.rerun()

    # Marker click → open panel (no extra st.rerun — st_folium already triggered one)
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
            # no st.rerun() — panel renders in this same pass

# ==============================================================================
# 8. RIGHT-HAND PANEL
# ==============================================================================
clicked_id  = st.session_state.get("clicked_place_id")
clicked_row = None
if clicked_id and df_pins is not None and not df_pins.empty:
    hit = df_pins[df_pins["place_id"] == clicked_id]
    if not hit.empty:
        clicked_row = hit.iloc[0]

if clicked_row is not None:
    cat   = clicked_row.get("master_category", "")
    color = CATEGORY_COLORS.get(cat, MUTED)
    avg   = float(clicked_row.get("bee_average", 0))
    count = int(clicked_row.get("bee_count", 0))
    rounded = int(round(avg))
    meter = "".join(
        f'<span class="{"" if (count and i <= rounded) else "off"}">🐝</span>'
        for i in range(1, 6)
    )
    score_text = f"{avg:.1f}" if count else "–"
    count_text = f"{count} bee rating{'s' if count != 1 else ''}" if count else "No ratings yet"
    enc  = urllib.parse.quote(clicked_id)
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
                <span class="bp-tag" style="background:{color}1f;color:{color};">
                    <i style="background:{color};"></i>{escape(str(cat))}
                </span>
                <div class="bp-name">{escape(str(clicked_row["name"]))}</div>
                <div class="bp-meta">{escape(str(clicked_row.get("district_name", "")))} · Berlin</div>
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
    # Native Streamlit button — positioned fixed via .st-key-bp_close CSS rule above
    if st.button("✕", key="bp_close"):
        st.session_state["clicked_place_id"] = None
        st.rerun()

elif selected_district != "City View (No Pins)" and df_pins is not None and not df_pins.empty:
    success = ""
    if "bee_rating_success" in st.session_state:
        success = f'<div class="bp-success">🐝 &nbsp;{escape(st.session_state.pop("bee_rating_success"))}</div>'

    visible_count = len(df_pins)
    rated_count   = int((df_pins["bee_count"] > 0).sum())
    total_ratings = int(df_pins["bee_count"].sum())
    view_average  = (
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
                    <div class="bp-top-name">{escape(str(r["name"]))}</div>
                    <div class="bp-top-meta">{escape(str(r["subcategory"]))} · {rating_count_label(int(r["bee_count"]))}</div>
                </div>
                <div style="text-align:right;">
                    {bee_meter_html(r["bee_average"])}
                    <div class="bp-top-score">{r["bee_average"]:.1f}/5</div>
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
                <div class="bp-desc">{escape(DISTRICT_STEREOTYPES.get(selected_district, ""))}</div>
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

# ==============================================================================
# 9. FLOATING LEGEND + CONTEXTUAL GUIDANCE
# ==============================================================================
if df_pins is not None and not df_pins.empty:
    _legend_items = [
        ("Food",      CATEGORY_COLORS["Food & Drink"]),
        ("Nightlife", CATEGORY_COLORS["Nightlife"]),
        ("Culture",   CATEGORY_COLORS["Culture & Heritage"]),
        ("Nature",    CATEGORY_COLORS["Nature & Outdoors"]),
        ("Transport", CATEGORY_COLORS["Public Transport"]),
    ]
    _legend_rows = "".join(
        f'<span class="item"><span class="dot" style="background:{c}"></span>{escape(l)}</span>'
        for l, c in _legend_items
    )
    _count = len(df_pins)
    st.markdown(
        f'<div class="bee-float-legend">'
        f'<div class="count">📍 {_count} place{"s" if _count != 1 else ""} shown</div>'
        f'<div class="row">{_legend_rows}</div></div>',
        unsafe_allow_html=True,
    )
elif selected_district == "City View (No Pins)":
    st.markdown(
        '<div class="bee-float-cta">👋 <b>Pick a district</b> above (or click one on the map) to start</div>',
        unsafe_allow_html=True,
    )
elif not (active_subcategories or show_public_transport):
    st.markdown(
        '<div class="bee-float-cta">✅ District set — now <b>choose a category</b> above</div>',
        unsafe_allow_html=True,
    )
elif df_pins is not None and df_pins.empty:
    st.markdown(
        '<div class="bee-float-cta">😕 <b>No matches</b> — widen your filters or lower the min 🐝</div>',
        unsafe_allow_html=True,
    )
