import duckdb
import geopandas as gpd
import pandas as pd
import numpy as np
import os

print("1. Loading and classifying Master POI file...")
master_file = "data/layer_master_berlin_pois.geojson"
gdf = gpd.read_file(master_file, engine="pyogrio")

# Safeguard against missing OSM tags
tags_to_check = ['amenity', 'tourism', 'historic', 'shop', 'leisure', 'natural', 'craft', 
                 'fee', 'wheelchair', 'lgbtq', 'gay', 'lesbian', 'transgender', 'diet:vegan', 'diet:vegetarian', 'name']
for col in tags_to_check:
    if col not in gdf.columns:
        gdf[col] = ''
    else:
        gdf[col] = gdf[col].fillna('')

# -- A. Assign Master Categories --
conditions = [
    gdf['amenity'].isin(['restaurant', 'fast_food', 'food_court', 'cafe', 'coffee_shop', 'bakery']) | gdf['shop'].isin(['bakery']),
    gdf['amenity'].isin(['bar', 'nightclub', 'brewery', 'wine_bar', 'marketplace']) | gdf['shop'].isin(['wine']) | gdf['craft'].isin(['brewery']),
    gdf['tourism'].isin(['museum', 'gallery', 'attraction', 'viewpoint']) | gdf['historic'].isin(['memorial', 'monument', 'city_gate', 'castle', 'building', 'ruins', 'checkpoint']) | (gdf['amenity'] == 'place_of_worship'),
    gdf['leisure'].isin(['park', 'garden', 'bathing_place']) | (gdf['natural'] == 'water') | (gdf.geometry.geom_type.isin(['LineString', 'MultiLineString']))
]
categories = ['Food & Drink', 'Nightlife', 'Culture & Heritage', 'Nature & Outdoors']
gdf['master_category'] = np.select(conditions, categories, default='Other')

# -- B. Assign Subcategories --
sub_conditions = [
    gdf['amenity'].isin(['cafe', 'coffee_shop']),
    gdf['amenity'].isin(['bakery']) | (gdf['shop'] == 'bakery'),
    gdf['amenity'].isin(['restaurant', 'fast_food', 'food_court']),
    gdf['amenity'] == 'nightclub',
    gdf['amenity'] == 'bar',
    gdf['amenity'].isin(['brewery', 'wine_bar']) | gdf['shop'].isin(['wine']) | gdf['craft'].isin(['brewery']),
    gdf['amenity'] == 'marketplace',
    gdf['tourism'] == 'museum',
    gdf['tourism'] == 'gallery',
    gdf['amenity'] == 'place_of_worship',
    gdf['leisure'].isin(['park', 'garden']),
    gdf['natural'] == 'water'
]
subcats = [
    'Cafes', 'Bakeries', 'Restaurants', 'Clubs', 'Bars', 'Breweries & Wine Bars', 
    'Markets', 'Museums', 'Galleries', 'Churches', 'Parks & Gardens', 'Lakes & Swimming'
]
gdf['subcategory'] = np.select(sub_conditions, subcats, default='Landmark or Trail')

# Fill missing names with their subcategory
gdf['name'] = np.where(gdf['name'] == '', 'Unnamed ' + gdf['subcategory'], gdf['name'])

# -- C. Boolean Filter Flags --
gdf['is_free'] = (gdf['fee'] == 'no') | gdf['leisure'].isin(['park']) | (gdf['master_category'] == 'Nature & Outdoors')
gdf['is_accessible'] = gdf['wheelchair'].isin(['yes', 'limited'])
gdf['is_lgbtq'] = gdf[['lgbtq', 'gay', 'lesbian', 'transgender']].apply(lambda row: any(val != '' and val != 'no' for val in row), axis=1)
gdf['is_vegan_friendly'] = gdf[['diet:vegan', 'diet:vegetarian']].apply(lambda row: any(val in ['yes', 'only'] for val in row), axis=1)

# -- D. Quality Score (0-5) --
# Counts how many useful OSM fields are filled in — used to surface well-documented places
gdf['quality_score'] = (
    (~gdf['name'].str.startswith('Unnamed')).astype(int) +
    (gdf['fee'] != '').astype(int) +
    (gdf['wheelchair'] != '').astype(int) +
    (gdf[['lgbtq', 'gay', 'lesbian', 'transgender']].ne('').any(axis=1)).astype(int) +
    (gdf[['diet:vegan', 'diet:vegetarian']].ne('').any(axis=1)).astype(int)
)

# Convert to standard Pandas dataframe for DuckDB ingestion
gdf['wkt_geometry'] = gdf.geometry.to_wkt()
df_pois = pd.DataFrame(gdf.drop(columns=['geometry']))

print("2. Initializing DuckDB and applying Spatial Join...")
con = duckdb.connect(database=':memory:')
con.execute("INSTALL spatial; LOAD spatial;")

# Register districts using Gemeinde_name to match your file
con.execute("""
    CREATE VIEW districts AS 
    SELECT Gemeinde_name AS district_name, geom AS district_geom
    FROM st_read('data/layer_districts.geojson');
""")

# Perform Spatial Join to assign districts
con.execute("""
    CREATE TABLE unified_pois AS
    SELECT
        p.name, p.master_category, p.subcategory,
        p.is_free, p.is_accessible, p.is_vegan_friendly, p.is_lgbtq,
        p.quality_score, d.district_name, p.wkt_geometry
    FROM df_pois AS p
    JOIN districts d ON st_intersects(st_geomfromtext(p.wkt_geometry), d.district_geom)
    WHERE p.master_category != 'Other';
""")

print("3. Ingesting Transit layer...")
transport_file = "data/layer_public_transportation_stops.txt"
if os.path.exists(transport_file):
    con.execute(f"""
        INSERT INTO unified_pois
        SELECT 
            stop_name AS name, 'Public Transport' AS master_category, 'Transit Stop' AS subcategory,
            true AS is_free, true AS is_accessible, false AS is_vegan_friendly, false AS is_lgbtq,
            3 AS quality_score, d.district_name, st_astext(st_point(stop_lon, stop_lat)) AS wkt_geometry
        FROM read_csv_auto('{transport_file}')
        JOIN districts d ON st_intersects(st_point(stop_lon, stop_lat), d.district_geom);
    """)

print("4. Exporting to Parquet...")
con.execute("COPY unified_pois TO 'data/berlin_pois.parquet' (FORMAT PARQUET);")
print("Database build complete! You can now run streamlit run app.py")