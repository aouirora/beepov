import os
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# ==============================================================================
# 1. PAGE & THEME CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="Berlin Tourist Map Explorer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Berlin Tourist Map Explorer")
st.markdown("Welcome to your interactive tour guide helper. Use the sidebar options to discover Berlin.")

# ==============================================================================
# 2. CACHED DATA LOADING FUNCTIONS
# ==============================================================================
@st.cache_data
def load_geojson_data(filepath, default_type="Attraction"):
    """Loads and normalizes standard GeoJSON layers."""
    if not os.path.exists(filepath):
        return gpd.GeoDataFrame(columns=['name', 'type', 'geometry'])
        
    gdf = gpd.read_file(filepath)
    
    # Extract the primary classification tag to create a clean display type
    if 'amenity' in gdf.columns and 'tourism' in gdf.columns:
        gdf['type'] = gdf['tourism'].fillna(gdf['amenity']).fillna(default_type)
    elif 'tourism' in gdf.columns:
        gdf['type'] = gdf['tourism'].fillna(default_type)
    elif 'amenity' in gdf.columns:
        gdf['type'] = gdf['amenity'].fillna(default_type)
    else:
        gdf['type'] = default_type
        
    # Ensure 'name' exists
    if 'name' not in gdf.columns:
        gdf['name'] = 'Unknown Site'
        
    return gdf[['name', 'type', 'geometry']].dropna(subset=['geometry'])

@st.cache_data
def load_transit_data(filepath):
    """Loads VBB transit text file and converts it to a clean spatial layer."""
    if not os.path.exists(filepath):
        return gpd.GeoDataFrame(columns=['stop_name', 'geometry'])
        
    df = pd.read_csv(filepath, usecols=["stop_name", "stop_lat", "stop_lon", "location_type"])
    # Keep only parent stations/hubs
    df = df[df["location_type"] == 1]
    df = df[df["stop_name"].str.contains("S\\+|U\\+|S\\+U", na=False)]
    
    gdf = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df.stop_lon, df.stop_lat),
        crs="EPSG:4326"
    )
    return gdf[['stop_name', 'geometry']]

# ==============================================================================
# 3. SIDEBAR CONTROLS & SELECTIONS
# ==============================================================================
st.sidebar.header("Map Configurations")

# Data File Paths (Updated to match your exact directory structure)
CULTURE_PATH = "data/layer_culture_landmarks.geojson"
NIGHTLIFE_PATH = "data/layer_nightlife_food_drinks.geojson"
TRANSIT_PATH = "data/layer_public_transportation_stops.txt"

# Trigger Data Load
with st.spinner("Loading Berlin spatial layers..."):
    culture_gdf = load_geojson_data(CULTURE_PATH, default_type="Culture/Landmark")
    nightlife_gdf = load_geojson_data(NIGHTLIFE_PATH, default_type="Food/Nightlife")
    transit_gdf = load_transit_data(TRANSIT_PATH)

# Interactive Toggles for Layers
st.sidebar.subheader("Active Layers")
show_culture = st.sidebar.checkbox("Show Culture & Landmarks", value=True)
show_nightlife = st.sidebar.checkbox("Show Nightlife & Food", value=False)
show_transit = st.sidebar.checkbox("Overlay Transit Hubs (S+U Bahn)", value=True)

# ==============================================================================
# 4. BUILDING THE FOLIUM MAP OBJECT
# ==============================================================================
st.subheader("Interactive Sightseeing Map")

# Initialize base map centered over downtown Berlin (Alexanderplatz area)
m = folium.Map(
    location=[52.5200, 13.4050], 
    zoom_start=13, 
    tiles="CartoDB positron" 
)

# Layer A: Plot Culture and Landmark Spots
if show_culture and not culture_gdf.empty:
    for _, row in culture_gdf.iterrows():
        if row.geometry.geom_type == 'Point':
            popup_html = f"<strong>{row['name']}</strong><br>Type: {str(row['type']).replace('_', ' ').title()}"
            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

# Layer B: Plot Nightlife and Food Spots
if show_nightlife and not nightlife_gdf.empty:
    for _, row in nightlife_gdf.iterrows():
        if row.geometry.geom_type == 'Point':
            popup_html = f"<strong>{row['name']}</strong><br>Type: {str(row['type']).replace('_', ' ').title()}"
            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color="orange", icon="glass")
            ).add_to(m)

# Layer C: Plot Public Transportation Overlay
if show_transit and not transit_gdf.empty:
    for _, row in transit_gdf.iterrows():
        if row.geometry.geom_type == 'Point':
            folium.Marker(
                location=[row.geometry.y, row.geometry.x],
                popup=folium.Popup(f"Transit: {row['stop_name']}", max_width=200),
                icon=folium.Icon(color="green", icon="train", prefix="fa")
            ).add_to(m)

# ==============================================================================
# 5. RENDERING IN STREAMLIT
# ==============================================================================
st_folium(m, width="100%", height=650, returned_objects=[])

st.info("Pro-Tip: Toggle layers in the sidebar to keep the map from getting cluttered.")