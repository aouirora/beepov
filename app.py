import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Set up the website layout
st.set_page_config(page_title="BeePOVMap Berlin", layout="wide")

# HEADER SECTION
st.title("🐝 BeePOVMap: Berlin Preference-Based Tourist Map")
st.write("Filter out the digital noise and find exactly what matches your vibe.")
st.markdown("---")

# LOAD DATA
@st.cache_data
def load_data():
    return pd.read_csv("berlin_pois.csv")

df = load_data()

# 🧠 THE MAGIC FIX: Track map state safely without infinite loops
if "map_center" not in st.session_state:
    st.session_state["map_center"] = [52.5162, 13.3999]
if "map_zoom" not in st.session_state:
    st.session_state["map_zoom"] = 12

# SIDEBAR FILTERS
st.sidebar.header("🗺️ Filter Your Berlin Experience")

selected_districts = st.sidebar.multiselect(
    "STEP 1: Choose One or More Districts",
    options=sorted(df['district'].unique().tolist()),
    default=sorted(df['district'].unique().tolist())
)

selected_categories = st.sidebar.multiselect(
    "STEP 2: Choose Activities",
    options=sorted(df['category'].unique().tolist()),
    default=sorted(df['category'].unique().tolist())
)

selected_subcategories = []
if selected_categories:
    available_subs = df[df['category'].isin(selected_categories)]['subcategory'].unique().tolist()
    selected_subcategories = st.sidebar.multiselect(
        "Narrow down your choices:",
        options=sorted(available_subs),
        default=sorted(available_subs)
    )

st.sidebar.markdown("---")
st.sidebar.subheader("✨ Optional Refinements")
filter_open_now = st.sidebar.toggle("Open Now Only")
filter_lgbtq = st.sidebar.toggle("LGBTQ+ / FLINTA Friendly")
filter_wheelchair = st.sidebar.toggle("Wheelchair Accessible ♿")
filter_free = st.sidebar.toggle("Free Entry / Budget (€) 🪙")

# FILTERING LOGIC
filtered_df = df.copy()
if selected_districts:
    filtered_df = filtered_df[filtered_df['district'].isin(selected_districts)]
if selected_categories:
    filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]
if selected_subcategories:
    filtered_df = filtered_df[filtered_df['subcategory'].isin(selected_subcategories)]
if filter_open_now:
    filtered_df = filtered_df[filtered_df['open_now'] == "Yes"]
if filter_lgbtq:
    filtered_df = filtered_df[filtered_df['lgbtq_friendly'] == "Yes"]
if filter_wheelchair:
    filtered_df = filtered_df[filtered_df['wheelchair_accessible'] == "Yes"]
if filter_free:
    filtered_df = filtered_df[filtered_df['free_entry'] == "Yes"]

# DISPLAY RESULTS & UPGRADED MAP LAYOUT
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📋 Match Results")
    st.write(f"Showing **{len(filtered_df)}** places matching your criteria.")
    if not filtered_df.empty:
        st.dataframe(filtered_df[['name', 'district', 'subcategory']], use_container_width=True)
    else:
        st.warning("No places match your criteria. Try adjusting filters!")

with col2:
    st.subheader("📍 Interactive Map")
    if not filtered_df.empty:
        # We read the stored memory coordinates so it stays exactly where you left it
        m = folium.Map(
            location=st.session_state["map_center"], 
            zoom_start=st.session_state["map_zoom"], 
            control_scale=True
        )
        
        marker_cluster = MarkerCluster().add_to(m)
        
        for index, row in filtered_df.iterrows():
            if row['category'] == 'Food & Drink':
                icon_color, icon_name = 'orange', 'coffee'
            elif row['category'] == 'Culture & Heritage':
                icon_color, icon_name = 'purple', 'landmark'
            elif row['category'] == 'Nightlife':
                icon_color, icon_name = 'darkpurple', 'music'
            else:
                icon_color, icon_name = 'green', 'tree'
                
            popup_html = f"""
                <div style="font-family: sans-serif; font-size: 13px; width: 200px;">
                    <h5 style="margin: 0 0 5px 0; color: #333;"><b>{row['name']}</b></h5>
                    <p style="margin: 0 0 5px 0; color: #777;"><i>{row['subcategory']}</i></p>
                    <hr style="margin: 5px 0; border: 0; border-top: 1px solid #ccc;">
                    <p style="margin: 2px 0;">🟢 <b>Open:</b> {row['open_now']}</p>
                    <p style="margin: 2px 0;">🏳️‍🌈 <b>LGBTQ+ Friendly:</b> {row['lgbtq_friendly']}</p>
                    <p style="margin: 2px 0;">♿ <b>Accessible:</b> {row['wheelchair_accessible']}</p>
                    <p style="margin: 2px 0;">🪙 <b>Free Entry:</b> {row['free_entry']}</p>
                </div>
            """
            
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix='fa')
            ).add_to(marker_cluster)
        
        # We tell the map renderer to ONLY give us back center and zoom adjustments
        map_output = st_folium(
            m, 
            width="100%", 
            height=500, 
            key="berlin_map", 
            returned_objects=["center", "zoom"]
        )
        
        # Safely save the location without triggering a rerun glitch
        if map_output and map_output.get("center"):
            new_lat = map_output["center"]["lat"]
            new_lng = map_output["center"]["lng"]
            new_zoom = map_output["zoom"]
            
            # Update memory silently so it's ready for the next filter click
            st.session_state["map_center"] = [new_lat, new_lng]
            st.session_state["map_zoom"] = new_zoom
            
    else:
        st.info("Select filters in the sidebar to populate the map pins.")