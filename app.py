import os
import streamlit as st
import duckdb
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import shapely.wkt

# ==============================================================================
# 1. INITIAL APP CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="BeePOV Map | Berlin", layout="wide")
st.title("BeePOV Map: Berlin Spatial Explorer")
st.markdown("Navigate Berlin without the cognitive overload. Select a neighborhood to begin.")

DISTRICT_CENTERS = {
    "Mitte": {"coords": [52.5200, 13.4050], "zoom": 14},
    "Friedrichshain-Kreuzberg": {"coords": [52.5050, 13.4400], "zoom": 14},
    "Neukölln": {"coords": [52.4800, 13.4350], "zoom": 14},
    "Charlottenburg-Wilmersdorf": {"coords": [52.5000, 13.2800], "zoom": 14},
    "Pankow": {"coords": [52.5600, 13.4000], "zoom": 13},
    "Tempelhof-Schöneberg": {"coords": [52.4700, 13.3800], "zoom": 13}
}

# ==============================================================================
# 2. CACHED DATABASE & DATA LOADERS
# ==============================================================================
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
# 3. TOP NAVIGATION FILTERS
# ==============================================================================
active_subcategories = []
show_public_transport = False
apply_free = False
apply_accessible = False
apply_vegan = False
apply_lgbtq = False
parent_categories_selected = set()
max_results = 15

if districts_gdf is not None:
    district_list = ["City View (No Pins)"] + sorted(list(DISTRICT_CENTERS.keys()))
else:
    district_list = ["City View (No Pins)"]

col_d, col_cats = st.columns([1, 3])

with col_d:
    selected_district = st.selectbox("📍 Select a District", district_list)

if selected_district != "City View (No Pins)":
    with col_cats:
        st.markdown("**Select Categories**")
        cat_cols = st.columns(5)
        with cat_cols[0]:
            food = st.checkbox("🍽 Food & Drink")
        with cat_cols[1]:
            nightlife = st.checkbox("🎵 Nightlife")
        with cat_cols[2]:
            culture = st.checkbox("🏛 Culture")
        with cat_cols[3]:
            nature = st.checkbox("🌿 Nature")
        with cat_cols[4]:
            transport = st.checkbox("🚌 Transport")

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

    query += " ORDER BY random() LIMIT 200"

    df_all = con.execute(query, params).df()

    if len(active_subcategories) > 1 and not df_all.empty:
        per_cat = max(1, max_results // len(active_subcategories))
        df_pins = (df_all.groupby('subcategory')
                         .apply(lambda x: x.head(per_cat))
                         .reset_index(drop=True))
    else:
        df_pins = df_all.head(max_results)

# ==============================================================================
# 5. RENDERING MAP VIEWPORT
# ==============================================================================
if selected_district == "City View (No Pins)":
    map_center = [52.5200, 13.4050]
    map_zoom = 11
else:
    map_center = DISTRICT_CENTERS[selected_district]["coords"]
    map_zoom = DISTRICT_CENTERS[selected_district]["zoom"]

m = folium.Map(location=map_center, zoom_start=map_zoom, tiles="CartoDB positron")

# Render Base District Borders
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

# Setup Marker Cluster
marker_cluster = MarkerCluster().add_to(m)

# Render Queried Pins into the Cluster
if df_pins is not None and not df_pins.empty:
    for _, row in df_pins.iterrows():
        try:
            point = shapely.wkt.loads(row['wkt_geometry'])
            if point.geom_type != 'Point': 
                point = point.centroid
        except Exception:
            continue
            
        cat = row.get('master_category', '')
        if cat == 'Culture & Heritage':
            icon_color, icon_type = 'blue', 'info-sign'
        elif cat == 'Nightlife':
            icon_color, icon_type = 'purple', 'glass'
        elif cat == 'Food & Drink':
            icon_color, icon_type = 'orange', 'cutlery'
        elif cat == 'Nature & Outdoors':
            icon_color, icon_type = 'green', 'leaf'
        elif cat == 'Public Transport':
            icon_color, icon_type = 'lightgray', 'unchecked'
        else:
            icon_color, icon_type = 'red', 'map-marker'
            
        subcat = str(row.get('subcategory', '')).replace('_', ' ').title()
        popup_html = f"<b>{row['name']}</b><br><i>{subcat}</i>"
            
        folium.Marker(
            location=[point.y, point.x],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color=icon_color, icon=icon_type)
        ).add_to(marker_cluster) # Added to Cluster instead of Base Map

st_folium(m, width="100%", height=700, returned_objects=[])