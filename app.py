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

# Check URL query parameters for ratings submitted via map popups
if "rate" in st.query_params and "place_id" in st.query_params:
    try:
        rate_val = int(st.query_params["rate"])
        place_id_val = st.query_params["place_id"]
        save_bee_rating(place_id_val, rate_val)
        st.session_state["bee_rating_success"] = f"Thanks! Your {rate_val}-Bee rating was added."
    except Exception:
        pass

    # If this request came from a popup click, render a success page in the new tab and close it
    if "close" in st.query_params:
        st.query_params.clear()
        st.markdown(
            """
            <div style="text-align: center; margin-top: 150px; font-family: sans-serif;">
                <h1 style="color: #2f2a1e; font-size: 2.2rem; margin-bottom: 0.5rem; font-weight: normal;">Rating Saved</h1>
                <p style="color: #756d5d; font-size: 1rem;">You can close this window now.</p>
            </div>
            <script>
                setTimeout(function() {
                    window.close();
                }, 800);
            </script>
            """,
            unsafe_allow_html=True
        )
        st.components.v1.html(
            """
            <script>
                window.close();
                setTimeout(function() {
                    parent.window.close();
                }, 300);
            </script>
            """,
            height=0,
            width=0
        )
        st.stop()

    # Clear query parameters to restore clean URL state
    st.query_params.clear()
    st.rerun()

# ==============================================================================
# 1. INITIAL APP CONFIGURATION & STYLING
# ==============================================================================
st.set_page_config(page_title="BeePOV Map | Berlin", layout="wide")
st.title("BeePOV Map: Berlin Spatial Explorer")
st.markdown("Navigate Berlin without the cognitive overload. Select a neighborhood to begin.")
st.markdown(
    """
    <style>
        .bee-rating-panel {
            border: 1px solid #ece7da;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            background: #fffdf8;
            margin-top: 0.75rem;
        }

        .bee-rating-heading {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            margin-bottom: 0.2rem;
            font-size: 1.08rem;
            font-weight: 650;
            color: #2f2a1e;
        }

        .bee-rating-subtle {
            color: #756d5d;
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .bee-summary-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.6rem;
            margin: 0.8rem 0 1rem;
        }

        .bee-summary-item {
            border: 1px solid #eee8da;
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
            background: #ffffff;
        }

        .bee-summary-label {
            color: #766f62;
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0;
        }

        .bee-summary-value {
            margin-top: 0.15rem;
            color: #2f2a1e;
            font-size: 1rem;
            font-weight: 650;
        }

        .bee-meter {
            display: inline-flex;
            align-items: center;
            gap: 0.2rem;
            vertical-align: middle;
        }

        .bee-meter .bee {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.45rem;
            height: 1.45rem;
            border-radius: 999px;
            border: 1px solid #e8dfca;
            background: #fff7df;
            font-size: 0.88rem;
            line-height: 1;
        }

        .bee-meter .bee-muted {
            background: #f5f3ee;
            filter: grayscale(1);
            opacity: 0.38;
        }

        .bee-score-line {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.55rem;
            margin: 0.45rem 0 0.8rem;
        }

        .bee-score-text {
            color: #645d51;
            font-size: 0.9rem;
        }

        .bee-top-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            border-top: 1px solid #eee8da;
            padding: 0.7rem 0;
        }

        .bee-top-row:first-child {
            border-top: 0;
        }

        .bee-place-name {
            color: #2f2a1e;
            font-weight: 650;
        }

        .bee-place-meta {
            color: #756d5d;
            font-size: 0.84rem;
            margin-top: 0.1rem;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.35rem;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] label {
            border: 1px solid #e8dfca;
            border-radius: 999px;
            padding: 0.3rem 0.58rem;
            background: #ffffff;
            min-width: 4.1rem;
            justify-content: center;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] label p {
            color: #1f1f1f;
            min-width: 2.15rem;
            text-align: center;
            white-space: nowrap;
        }

        div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
            border-color: #d4b75f;
            background: #fff9e8;
        }

        @media (max-width: 760px) {
            .bee-summary-grid {
                grid-template-columns: 1fr;
            }

            .bee-top-row {
                align-items: flex-start;
                flex-direction: column;
            }
        }
    </style>
    """,
    unsafe_allow_html=True
)

DISTRICT_CENTERS = {
    "Mitte": {"coords": [52.5200, 13.4050], "zoom": 14},
    "Friedrichshain-Kreuzberg": {"coords": [52.5050, 13.4400], "zoom": 14},
    "Neukölln": {"coords": [52.4800, 13.4350], "zoom": 14},
    "Charlottenburg-Wilmersdorf": {"coords": [52.5000, 13.2800], "zoom": 14},
    "Pankow": {"coords": [52.5600, 13.4000], "zoom": 13},
    "Tempelhof-Schöneberg": {"coords": [52.4700, 13.3800], "zoom": 13}
}

DISTRICT_STEREOTYPES = {
    "Mitte": "Historically Berlin's core, Mitte is now the polished, corporate, and tourist center. It is characterized by high-end startup offices, government buildings, busy shopping districts, and chic cafes.",
    "Friedrichshain-Kreuzberg": "The alternative heart of Berlin. Famous for its legendary techno clubs, punk heritage, colorful street art, and vibrant political activism.",
    "Neukölln": "Raw, edgy, and rapidly changing. Neukölln is famous for its diverse, multicultural atmosphere, international street food, smoky hipster bars, and proximity to the Tempelhofer Feld.",
    "Charlottenburg-Wilmersdorf": "The wealthy, elegant heart of old West Berlin. It is known for its beautiful pre-war buildings, upscale dining, peaceful residential areas, and luxury shopping along Kurfürstendamm.",
    "Pankow": "Berlin's family-friendly haven (including Prenzlauer Berg). Popularly stereotyped as a cozy neighborhood of renovated apartments, organic food markets, baby strollers, and relaxed cafes.",
    "Tempelhof-Schöneberg": "A leafy district that is historically the heart of Berlin's LGBTQ+ community. It features cozy local pubs, quiet residential areas, and borders the massive former Tempelhof Airport runway park."
}

RATINGS_PATH = "data/bee_ratings.json"

# ==============================================================================
# 2. HELPER FUNCTIONS & DATA LOADERS
# ==============================================================================
def get_place_id(row):
    return "|".join([
        str(row.get('name', 'Unknown place')),
        str(row.get('district_name', 'Unknown district')),
        str(row.get('master_category', '')),
        str(row.get('subcategory', '')),
    ])

def format_bees(rating):
    if rating <= 0:
        return "No Bee ratings yet"
    full_bees = int(round(rating))
    return "🐝" * full_bees + "·" * (5 - full_bees)

def bee_meter_html(rating):
    active_bees = int(round(rating))
    bees = []
    for bee_number in range(1, 6):
        bee_class = "bee" if bee_number <= active_bees else "bee bee-muted"
        bees.append(f'<span class="{bee_class}">🐝</span>')
    return f'<span class="bee-meter">{"".join(bees)}</span>'

def rating_count_label(count):
    return f"{count} rating{'s' if count != 1 else ''}"

def get_rating_summary(ratings, place_id):
    place_ratings = ratings.get(place_id, [])
    if not place_ratings:
        return 0, 0
    return sum(place_ratings) / len(place_ratings), len(place_ratings)



@st.cache_resource
def get_database_connection():
    con = duckdb.connect(database=':memory:')
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
# 3. STATE INITIALIZATION & TOP NAVIGATION FILTERS
# ==============================================================================
if "selected_district" not in st.session_state:
    st.session_state["selected_district"] = "City View (No Pins)"

if "shuffle_seed" not in st.session_state:
    st.session_state["shuffle_seed"] = "beepov-default"

if "clicked_place_id" not in st.session_state:
    st.session_state["clicked_place_id"] = None

# GEOLOCATION FEATURE START
if "use_user_location" not in st.session_state:
    st.session_state["use_user_location"] = False
if "user_lat" not in st.session_state:
    st.session_state["user_lat"] = None
if "user_lon" not in st.session_state:
    st.session_state["user_lon"] = None
if "geo_widget_shown" not in st.session_state:
    st.session_state["geo_widget_shown"] = False
# GEOLOCATION FEATURE END

active_subcategories = []
show_public_transport = False
apply_free = False
apply_accessible = False
apply_vegan = False
apply_lgbtq = False
minimum_bee_rating = 0
parent_categories_selected = set()
max_results = 15

if districts_gdf is not None:
    district_list = ["City View (No Pins)"] + sorted(list(DISTRICT_CENTERS.keys()))
else:
    district_list = ["City View (No Pins)"]

# --- THE CLEAN SYNC FIX ---
# Calculate which index the dropdown should visually show
try:
    current_index = district_list.index(st.session_state["selected_district"])
except ValueError:
    current_index = 0

# GEOLOCATION FEATURE START
col_d, col_info, col_loc, col_cats = st.columns([1.5, 0.4, 1.1, 3])
# GEOLOCATION FEATURE END

with col_d:
    # Render the selectbox WITHOUT a key, and grab its returned value
    ui_selection = st.selectbox(
        "📍 Select a District",
        options=district_list,
        index=current_index
    )

    # If the user clicks the dropdown, update the state and immediately rerun
    if ui_selection != st.session_state["selected_district"]:
        st.session_state["selected_district"] = ui_selection
        st.rerun()

with col_info:
    st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical alignment spacer
    selected_district = st.session_state["selected_district"]
    if selected_district != "City View (No Pins)":
        with st.popover("ℹ️", help="District Vibe & Stereotype"):
            st.markdown(f"**{selected_district} vibe**")
            st.write(DISTRICT_STEREOTYPES.get(selected_district, ""))

# GEOLOCATION FEATURE START
with col_loc:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    if st.button("📍 Use My Location"):
        st.session_state["use_user_location"] = True

    if st.session_state["use_user_location"]:
        location = streamlit_geolocation()
        if location and location.get("latitude") is not None and location.get("longitude") is not None:
            st.session_state["user_lat"] = location["latitude"]
            st.session_state["user_lon"] = location["longitude"]
        elif st.session_state["geo_widget_shown"] and st.session_state["user_lat"] is None:
            # The streamlit-geolocation component never reports a distinct "denied"
            # state (a browser rejection just leaves its value at the default), so a
            # still-empty result on a render after the widget was shown is treated as denial.
            st.session_state["use_user_location"] = False
            st.warning("Location access was denied. Please enable location permissions in your browser.")
        st.session_state["geo_widget_shown"] = True
# GEOLOCATION FEATURE END

# For the rest of the app, use the clean session state variable
selected_district = st.session_state["selected_district"]

if selected_district != "City View (No Pins)":
    with col_cats:
        st.markdown("**Select Categories**")
        cat_cols = st.columns(5)
        with cat_cols[0]: food = st.checkbox("🍽 Food & Drink")
        with cat_cols[1]: nightlife = st.checkbox("🎵 Nightlife")
        with cat_cols[2]: culture = st.checkbox("🏛 Culture")
        with cat_cols[3]: nature = st.checkbox("🌿 Nature")
        with cat_cols[4]: transport = st.checkbox("🚌 Transport")

    if food or nightlife or culture or nature or transport:
        st.markdown("---")
        sub_cols = st.columns([2, 2, 2, 2, 1])

        if food:
            parent_categories_selected.add('Food & Drink')
            with sub_cols[0]:
                st.markdown("**Food & Drink**")
                if st.checkbox("Restaurants", value=True, key="sub_rest"): active_subcategories.append('Restaurants')
                if st.checkbox("Cafes", value=True, key="sub_cafe"): active_subcategories.append('Cafes')
                if st.checkbox("Bakeries & Street Food", value=True, key="sub_bake"): active_subcategories.extend(['Bakeries', 'Markets'])

        if nightlife:
            parent_categories_selected.add('Nightlife')
            with sub_cols[1]:
                st.markdown("**Nightlife**")
                if st.checkbox("Bars & Pubs", value=True, key="sub_bars"): active_subcategories.append('Bars')
                if st.checkbox("Clubs", value=True, key="sub_clubs"): active_subcategories.append('Clubs')
                if st.checkbox("Breweries & Wine Bars", value=True, key="sub_brew"): active_subcategories.append('Breweries & Wine Bars')

        if culture:
            parent_categories_selected.add('Culture & Heritage')
            with sub_cols[2]:
                st.markdown("**Culture & Heritage**")
                if st.checkbox("Museums & Galleries", value=True, key="sub_mus"): active_subcategories.extend(['Museums', 'Galleries'])
                if st.checkbox("Landmarks", value=True, key="sub_land"): active_subcategories.append('Landmark or Trail')
                if st.checkbox("Churches", value=True, key="sub_church"): active_subcategories.append('Churches')

        if nature:
            parent_categories_selected.add('Nature & Outdoors')
            with sub_cols[3]:
                st.markdown("**Nature & Outdoors**")
                if st.checkbox("Parks & Gardens", value=True, key="sub_parks"): active_subcategories.append('Parks & Gardens')
                if st.checkbox("Lakes", value=True, key="sub_lakes"): active_subcategories.append('Lakes & Swimming')
                if st.checkbox("Hiking & Trails", value=True, key="sub_hike"): active_subcategories.append('Hiking & Bike Trails')

        if transport:
            parent_categories_selected.add('Public Transport')
            show_public_transport = True

        with sub_cols[4]:
            st.markdown("**Refine**")
            apply_free = st.checkbox("Free")
            apply_accessible = st.checkbox("Accessible")
            if food or nightlife:
                apply_vegan = st.checkbox("Vegan")
            apply_lgbtq = st.checkbox("LGBTQ+")
            max_results = st.slider("Max", min_value=5, max_value=50, value=15)
            minimum_bee_rating = st.slider("Min 🐝", min_value=0, max_value=5, value=0)
            if st.button("🔀 Shuffle"):
                st.session_state["shuffle_seed"] = datetime.utcnow().isoformat()

st.markdown("---")

# ==============================================================================
# 4. DATABASE QUERY CONSTRUCTION (DUCKDB)
# ==============================================================================
df_pins = None

if selected_district != "City View (No Pins)" and (active_subcategories or show_public_transport) and os.path.exists('data/berlin_pois.parquet'):

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
        df_pins = pd.concat(
            [grp.head(per_cat) for _, grp in df_all.groupby('subcategory')]
        ).reset_index(drop=True)
    else:
        df_pins = df_all.head(max_results).copy()

bee_ratings = load_bee_ratings()

if df_pins is not None and not df_pins.empty:
    df_pins["place_id"] = df_pins.apply(get_place_id, axis=1)
    rating_summaries = df_pins["place_id"].apply(lambda place_id: get_rating_summary(bee_ratings, place_id))
    df_pins["bee_average"] = rating_summaries.apply(lambda s: s[0])
    df_pins["bee_count"] = rating_summaries.apply(lambda s: s[1])

    if minimum_bee_rating > 0:
        df_pins = df_pins[
            (df_pins["bee_count"] > 0) & (df_pins["bee_average"] >= minimum_bee_rating)
        ]

# ==============================================================================
# 5. RENDERING MAP VIEWPORT & CLICK LOGIC
# ==============================================================================
# GEOLOCATION FEATURE START
if (
    st.session_state["use_user_location"]
    and st.session_state["user_lat"] is not None
    and st.session_state["user_lon"] is not None
):
    map_center = [st.session_state["user_lat"], st.session_state["user_lon"]]
    map_zoom = 15
elif selected_district == "City View (No Pins)":
    map_center = [52.5200, 13.4050]
    map_zoom = 11
else:
    map_center = DISTRICT_CENTERS[selected_district]["coords"]
    map_zoom = DISTRICT_CENTERS[selected_district]["zoom"]
# GEOLOCATION FEATURE END

m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="CartoDB positron")

if districts_gdf is not None:
    def get_district_style(feature):
        d_name = feature['properties'].get('Gemeinde_name', feature['properties'].get('name', ''))
        if selected_district != "City View (No Pins)" and d_name == selected_district:
            return {'fillColor': '#3186cc', 'color': '#3186cc', 'fillOpacity': 0.15, 'weight': 2}
        return {'fillColor': '#eaeaea', 'color': '#b5b5b5', 'fillOpacity': 0.05, 'weight': 1}

    folium.GeoJson(
        districts_gdf,
        style_function=get_district_style
    ).add_to(m)

marker_cluster = MarkerCluster().add_to(m)

if df_pins is not None and not df_pins.empty:
    for _, row in df_pins.iterrows():
        try:
            point = shapely.wkt.loads(row['wkt_geometry'])
            if point.geom_type != 'Point':
                point = point.centroid
        except Exception:
            continue

        cat = row.get('master_category', '')
        if cat == 'Culture & Heritage': icon_color, icon_type = 'blue', 'info-sign'
        elif cat == 'Nightlife': icon_color, icon_type = 'purple', 'glass'
        elif cat == 'Food & Drink': icon_color, icon_type = 'orange', 'cutlery'
        elif cat == 'Nature & Outdoors': icon_color, icon_type = 'green', 'leaf'
        elif cat == 'Public Transport': icon_color, icon_type = 'lightgray', 'unchecked'
        else: icon_color, icon_type = 'red', 'map-marker'

        subcat = str(row.get('subcategory', '')).replace('_', ' ').title()
        bee_average = float(row.get('bee_average', 0))
        bee_count = int(row.get('bee_count', 0))
        if bee_count:
            rating_line = f"{bee_average:.1f}/5 from {bee_count} rating{'s' if bee_count != 1 else ''}"
        else:
            rating_line = "No Bee ratings yet"
        escaped_place_id = urllib.parse.quote(row['place_id'])
        rating_links_html = f"""
        <div style="margin-top: 8px; border-top: 1px solid #eee; padding-top: 6px; font-family: sans-serif; width: 100%;">
            <div style="font-size: 11px; color: #756d5d; margin-bottom: 5px; font-weight: bold;">Rate this place:</div>
            <div style="display: flex; gap: 4px; flex-wrap: nowrap; justify-content: space-between;">
                <a href="/?rate=1&place_id={escaped_place_id}&" target="_self" style="display: inline-block; padding: 2px 6px; background: #fff7df; border: 1px solid #e8dfca; border-radius: 4px; text-decoration: none; font-size: 11px; color: #2f2a1e; font-weight: bold; min-width: 30px; text-align: center;">1🐝</a>
                <a href="/?rate=2&place_id={escaped_place_id}&" target="_self" style="display: inline-block; padding: 2px 6px; background: #fff7df; border: 1px solid #e8dfca; border-radius: 4px; text-decoration: none; font-size: 11px; color: #2f2a1e; font-weight: bold; min-width: 30px; text-align: center;">2🐝</a>
                <a href="/?rate=3&place_id={escaped_place_id}&" target="_self" style="display: inline-block; padding: 2px 6px; background: #fff7df; border: 1px solid #e8dfca; border-radius: 4px; text-decoration: none; font-size: 11px; color: #2f2a1e; font-weight: bold; min-width: 30px; text-align: center;">3🐝</a>
                <a href="/?rate=4&place_id={escaped_place_id}&" target="_self" style="display: inline-block; padding: 2px 6px; background: #fff7df; border: 1px solid #e8dfca; border-radius: 4px; text-decoration: none; font-size: 11px; color: #2f2a1e; font-weight: bold; min-width: 30px; text-align: center;">4🐝</a>
                <a href="/?rate=5&place_id={escaped_place_id}&" target="_self" style="display: inline-block; padding: 2px 6px; background: #fff7df; border: 1px solid #e8dfca; border-radius: 4px; text-decoration: none; font-size: 11px; color: #2f2a1e; font-weight: bold; min-width: 30px; text-align: center;">5🐝</a>
            </div>
        </div>
        """
        popup_html = f"<b>{escape(str(row['name']))}</b><br><i>{escape(subcat)}</i><br><span>{escape(rating_line)}</span>{rating_links_html}"

        folium.Marker(
            location=[point.y, point.x],
            popup=folium.Popup(popup_html, max_width=270),
            icon=folium.Icon(color=icon_color, icon=icon_type)
        ).add_to(marker_cluster)

# GEOLOCATION FEATURE START
if (
    st.session_state["use_user_location"]
    and st.session_state["user_lat"] is not None
    and st.session_state["user_lon"] is not None
):
    folium.Marker(
        location=[st.session_state["user_lat"], st.session_state["user_lon"]],
        popup=folium.Popup("You are here", max_width=200),
        icon=folium.Icon(color="blue", icon="user")
    ).add_to(m)
# GEOLOCATION FEATURE END

# Create columns for Map (left) and Details/Rating Panel (right)
col_map, col_panel = st.columns([5, 2])

with col_map:
    # Create the map and listen for clicks
    map_data = st_folium(
        m,
        height=700,
        use_container_width=True,
        returned_objects=["last_active_drawing", "last_object_clicked"]
    )

# The Click Handler
if map_data:
    # 1. Handle district click (GeoJson feature)
    if map_data.get("last_active_drawing"):
        clicked_properties = map_data["last_active_drawing"].get("properties", {})
        clicked_district = clicked_properties.get("Gemeinde_name", clicked_properties.get("name", ""))

        if clicked_district and clicked_district in DISTRICT_CENTERS:
            # If the map click is different from our current view, update and reload!
            if st.session_state["selected_district"] != clicked_district:
                # Update our absolute source of truth and rerun
                st.session_state["selected_district"] = clicked_district
                st.session_state["clicked_place_id"] = None  # Reset selection on district change
                st.rerun()

    # 2. Handle marker click
    if map_data.get("last_object_clicked"):
        clicked_lat = map_data["last_object_clicked"]["lat"]
        clicked_lng = map_data["last_object_clicked"]["lng"]

        matched_place_id = None
        if df_pins is not None and not df_pins.empty:
            for _, row in df_pins.iterrows():
                try:
                    point = shapely.wkt.loads(row['wkt_geometry'])
                    if point.geom_type != 'Point':
                        point = point.centroid
                    if abs(point.y - clicked_lat) < 1e-5 and abs(point.x - clicked_lng) < 1e-5:
                        matched_place_id = row["place_id"]
                        break
                except Exception:
                    continue

        if matched_place_id and st.session_state.get("clicked_place_id") != matched_place_id:
            st.session_state["clicked_place_id"] = matched_place_id
            st.rerun()


# ==============================================================================
# 6. BEE RATING SYSTEM (SIDE PANEL)
# ==============================================================================
with col_panel:
    if selected_district == "City View (No Pins)" or df_pins is None:
        st.markdown(
            """
            <div class="bee-rating-panel" style="margin-top: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; color: #756d5d; min-height: 250px;">
                <h4 style="color: #2f2a1e; margin-bottom: 0.4rem;">No neighborhood active</h4>
                <p style="font-size: 0.88rem; margin: 0 1rem; line-height: 1.4;">Select a district at the top of the screen to load places of interest and start rating.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif df_pins.empty:
        st.info("No places match the current filters and Bee rating threshold.")
    else:
        rating_options = {
            f"{row['name']} ({row['subcategory']})": row["place_id"]
            for _, row in df_pins.sort_values("name").iterrows()
        }
        visible_count = len(df_pins)
        rated_places_count = int((df_pins["bee_count"] > 0).sum())
        total_ratings = int(df_pins["bee_count"].sum())
        view_average = 0
        if total_ratings:
            view_average = (
                (df_pins["bee_average"] * df_pins["bee_count"]).sum() / total_ratings
            )

            if "bee_rating_success" in st.session_state:
                st.success(st.session_state.pop("bee_rating_success"))

        # Get the currently selected place from the map
        selected_place = None

        if st.session_state.get("clicked_place_id"):
            selected_rows = df_pins[
                df_pins["place_id"] == st.session_state["clicked_place_id"]
            ]

            if not selected_rows.empty:
                selected_place = selected_rows.iloc[0]

        st.markdown(
            f"""
            <section class="bee-rating-panel" style="margin-top: 0;">
                <div class="bee-rating-heading"><span>🐝</span><span>{selected_district} Overview</span></div>
                <div class="bee-rating-subtle" style="margin-bottom: 0.6rem;">
                    Click any marker on the map and select a rating (1-5 Bees) directly inside the popup.
                </div>
                <div class="bee-summary-grid" style="margin-top: 0; margin-bottom: 0;">
                    <div class="bee-summary-item">
                        <div class="bee-summary-label">Visible</div>
                        <div class="bee-summary-value">{visible_count}</div>
                    </div>
                    <div class="bee-summary-item">
                        <div class="bee-summary-label">Rated</div>
                        <div class="bee-summary-value">{rated_places_count}</div>
                    </div>
                    <div class="bee-summary-item">
                        <div class="bee-summary-label">Average</div>
                        <div class="bee-summary-value">{view_average:.1f}/5</div>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True
        )

        # Expander for manual rating from list (fallback)
        with st.expander("Or select place from list to rate"):
            with st.form("bee_rating_form_fallback", clear_on_submit=False, border=True):
                selected_place_label = st.selectbox("Place", list(rating_options.keys()))
                fallback_place_id = rating_options[selected_place_label]
                selected_average, selected_count = get_rating_summary(bee_ratings, fallback_place_id)
                if selected_count:
                    selected_score_text = f"{selected_average:.1f}/5 from {rating_count_label(selected_count)}"
                else:
                    selected_score_text = "No ratings yet"

                st.markdown(
                    f"""
                    <div class="bee-score-line" style="margin-top: 0; margin-bottom: 0.6rem;">
                        {bee_meter_html(selected_average)}
                        <span class="bee-score-text">{selected_score_text}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                selected_bee_rating = st.radio(
                    "Your Bee rating",
                    options=[1, 2, 3, 4, 5],
                    horizontal=True,
                    format_func=lambda rating: f"{rating} 🐝",
                    key="fallback_radio"
                )
                submitted_rating = st.form_submit_button("Submit Bee Rating")

            if submitted_rating:
                save_bee_rating(fallback_place_id, selected_bee_rating)
                st.session_state["bee_rating_success"] = (
                    f"Thanks! Your {selected_bee_rating}-Bee rating was added."
                )
                st.rerun()

        # Top Bee-rated places
        rated_places = df_pins[df_pins["bee_count"] > 0].copy()
        if not rated_places.empty:
            rated_places = rated_places.sort_values(["bee_average", "bee_count"], ascending=False).head(5)
            st.markdown("#### Top Bee-rated places")
            for _, row in rated_places.iterrows():
                bee_count = int(row["bee_count"])
                st.markdown(
                    f"""
                    <div class="bee-top-row">
                        <div>
                            <div class="bee-place-name">{escape(str(row['name']))}</div>
                            <div class="bee-place-meta">{escape(str(row['subcategory']))} · {rating_count_label(bee_count)}</div>
                        </div>
                        <div class="bee-score-line">
                            {bee_meter_html(row['bee_average'])}
                            <span class="bee-score-text">{row['bee_average']:.1f}/5</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )