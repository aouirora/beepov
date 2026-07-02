# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Rebuild the POI Parquet (only needed after updating raw GeoJSON source data)
python build_database.py

# Run the app locally
streamlit run app.py
```

There is no test suite and no linter configured.

## Architecture

**BeePOV** is a single-page Streamlit app (`app.py`) that renders an interactive Folium map of Berlin POIs with preference-based filtering.

### Data flow

```
data/layer_master_berlin_pois.geojson   ← raw OSM data (committed)
        │
        ▼  build_database.py
data/berlin_pois.parquet                ← queryable POI table (committed)
        │
        ▼  DuckDB query in app.py (Section 6)
data/beepov.db (reviews table)          ← user ratings (gitignored, runtime only)
        │
        ▼  Folium + st_folium
Interactive map
```

`build_database.py` is a one-shot ETL script: it reads the master GeoJSON, assigns master categories and subcategories from OSM tags, computes boolean filter flags (`is_free`, `is_accessible`, `is_vegan_friendly`, `is_lgbtq`) and a `quality_score` (0–3 based on data completeness), performs a spatial join to assign each POI to a Berlin district, deduplicates trail segments, and writes `data/berlin_pois.parquet`.

### app.py structure

The file is divided into numbered sections (comments mark each):

| Section | Contents |
|---|---|
| 0 | DuckDB connection (`@st.cache_resource`), `save_bee_rating()`, query-param rating handler |
| 1 | `st.set_page_config` + all CSS (design tokens, honeycomb buttons, sliding panel, legend) |
| 2 | `CATEGORIES` list (keys, labels, subcategory values), `DISTRICT_CENTERS`, `DISTRICT_STEREOTYPES` |
| 3 | `_district_style()`, `_build_folium_map()` (`@st.cache_data`), `load_districts_layer()` |
| 4 | `st.session_state` initialization |
| 5 | Top bar: brand, district selectbox, search input, geolocation widget, honeycomb category toggles, Filters popover |
| 6 | DuckDB SELECT against `berlin_pois.parquet` LEFT JOIN `reviews`, with all active filter conditions |
| 7 | `_build_folium_map()` call → `st_folium()` render → click handling |
| 8 | Right-hand sliding panel: place detail + bee rating UI, or district overview when no pin is selected |
| 9 | Floating bottom-left legend + contextual guidance CTA |

### Key design decisions

**Map caching**: `_build_folium_map` is `@st.cache_data` keyed on map center, zoom, district, a hash of visible pin IDs, and geolocation state. `clicked_place_id` is intentionally excluded from the cache key — this prevents the Leaflet iframe from being recreated (and flashing) when the user clicks a pin. The detail panel is rendered in the same Python pass from `st.session_state`.

**Rating flow via query params**: The bee-rating UI is HTML anchor links with `?rate=N&place_id=X`. On the next page load, Section 0 reads these params, writes to the `reviews` table, restores `clicked_place_id` to keep the panel open, and calls `st.rerun()` to clear the params. The `reviews` table lives in `data/beepov.db` (DuckDB), which is gitignored.

**Quality score filtering**: The DuckDB query (Section 6) applies `quality_score >= 2` for all categories except Nature & Outdoors, which uses `quality_score >= 1`. This is intentional — nature POIs often have sparse OSM metadata but are still valid.

**No `app/` directory**: Everything is in the root `app.py`. The `app/` directory exists as an empty placeholder.

### Data files

| File | Status | Purpose |
|---|---|---|
| `data/berlin_pois.parquet` | committed | Main POI table, queried at runtime |
| `data/layer_districts.geojson` | committed | District boundary polygons for map overlay |
| `data/layer_master_berlin_pois.geojson` | committed | Source GeoJSON for ETL |
| `data/beepov.db` | **gitignored** | Runtime DuckDB with `reviews` table |
| `data/bee_ratings.json` | **gitignored** | Legacy ratings file (superseded by DB) |
