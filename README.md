# BeePOV Map
> A map of Berlin designed to reduce cognitive overload through preference based filtering.
---

## Table of Contents

- [Background](#background)
- [User Research](#user-research)
- [Mission Statement](#mission-statement)
- [Data and System Architecture](#data-and-system-architecture)
- [Filter Structure](#filter-structure)
- [Usage](#usage)

---

## Background
According to visitBerlin, around 12.1 million visitors came to Berlin in 2023, generating approximately 29.6 million overnight stays, with international guests exceeding 40% of total visitors for the first time since 2019. (visitBerlin, 2024).

Existing research on choice overload in tourism shows that destination decision-making is strongly affected by the number of available options. Large choice sets increase cognitive load and make decisions more difficult, which reduces satisfaction and increases regret, particularly when tourists perceive options as too similar to meaningfully compare. Crucially, these negative effects can be reduced when information is presented sequentially rather than all at once (Luo et al., 2026).

In today's mobile and "all-media" tourism environment, tourists are exposed to large amounts of information that can exceed their cognitive capacity. This leads to cognitive confusion, lower decision-making efficiency, and negative emotional responses. Simplifying information presentation and improving trust mechanisms can significantly improve tourism information systems (Liu, 2025). A separate study confirms that larger tourism choice sets increase decision complexity, resulting in a paradox of choice that negatively affects the overall decision-making process (Park & Eves, 2023).

### References

1. visitBerlin (2024). *2023: Berlin tourism continues to rise.* https://about.visitberlin.de/en/press/press-releases/2023-berlin-tourism-continue-rise
2. Luo, H., Lu, L., Liang, Z., & Su, S. (2026). Navigating Choice Overload: How time pressure and visual display shape tourist decisions. *Journal of Travel Research.* https://doi.org/10.1177/00472875261424436
3. Liu, J. (2025). The impact of information overload on preferences for tourism information media. *Finance & Economics, 1*(6). https://doi.org/10.61173/5cscss44
4. Park, S., & Eves, A. (2023). Choice Overload in tourism: Moderating roles of hypothetical and social distance. *Journal of Travel Research, 63*(7), 1626–1641. https://doi.org/10.1177/00472875231197379

---

## User Research

### Survey

To understand the problem from the user's perspective, we distributed a survey to tourists visiting Berlin and residents who regularly guide visitors. The survey contains five sections:

- **Screening & Demographics**: visitor type, Berlin familiarity, frequency of digital map usage
- **Current Behavior**: tools used to discover places (Google Maps, TikTok, Instagram, Reddit, TripAdvisor, etc.) and typical search interests (restaurants, museums, nightlife, hidden gems, etc.)
- **Problem Ranking**: participants ranked frustrations including too many choices, difficulty matching interests, unclear recommendations, app-switching, and route planning difficulty
- **Existing Alternatives**: open-ended exploration of current workflows, pain points, and personal shortcuts
- **Early Adopter Signals**: importance of finding places that match personal preferences

### Persona Definition

**Name:** Mara  
**Age:** 25  
**Bio:** A frequent visitor to Berlin who knows the city well, but that familiarity hasn't made planning easier. Every trip, she finds herself switching multiple apps, scrolling through endless recommendations, and still struggling to decide where to go. Mara has too much tourist information,andwhat she's missing is a way to cut through the noise and quickly surface places that actually match her taste.  
**Tools she uses:** Mara uses Google Maps multiple times a day and relies heavily on Instagram and TikTok for discovery. She often has three apps open at once, cross-referencing recommendations before committing to anything.  
**What she likes:**  
- Cafés, museums, parks, and cultural spots with a local feel
- Recommendations from friends or people with similar taste — she typically needs to see a place mentioned 3–4 times before she'll visit
- Hidden gems and neighbourhood spots that aren't already saturated with tourists
- She loves how every Berlin district has its own distinct personality, and that's what keep bringing her back to explore ones she hasn't fully discovered yet.

**Frustrations:**   
- The more options she sees, the harder it is to choose — she often can't decide or just picks something randomly
- Switching between apps to check a single place takes too much time and energy
- Even though she knows the city well, planning still feels like starting over every time
- After finally picking a place, she still wonders if she chose the wrong one

>*Mara: "This is my fifth time here, but I still spend an hour on my phone going through app after app, and by the end I feel more lost than when I started."*

---

## Mission Statement  
> To develop a proof of concept of a dashboard. The dashboard will present an interactive map of Berlin with filters for points of interest. The dashboard will help tourists find places that match their preferences more easily. This reduces the number of irrelevant options and prevents information overload. The proof of concept will enable the owner to assess the potential of preference-based filtering. This could improve tourists’ navigation of Berlin’s diverse city landscape.
---

## Data and System Architecture

### Data
 
| Category | Source | Format |
|---|---|---|
| District boundaries | Berlin Open Data Portal — [daten.odis-berlin.de](https://daten.odis-berlin.de) | GeoJSON |
| Nightlife & Food & Drink | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Culture & Heritage | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Nature & Outdoors | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Public transport stops | VBB Open Data — [unternehmen.vbb.de](https://unternehmen.vbb.de/digitale-services/datensaetze/) | CSV |
| Hotels & tourism | Berlin Open Data — [daten.berlin.de](https://daten.berlin.de/datensaetze/tourismus-in-berlin) | XLS |
| Street parades & markets | Berlin Open Data — [daten.berlin.de](https://daten.berlin.de/datensaetze/simple_search_wwwberlindesenwebservicemaerktefestestrassenvolksfeste) | GeoJSON |
 
Overpass queries use standard OSM tags (`amenity`, `tourism`, `leisure`, `natural`, `historic`, `craft`) to extract Berlin POIs by category, all scoped to the Berlin administrative boundary via `{{geocodeArea:Berlin}}`. All queries follow the same structure, only the tags inside the filter block vary.
 
<details>
<summary>Example query: Nightlife & Food & Drink</summary>
    
```
[out:json][timeout:90];
{{geocodeArea:Berlin}}->.searchArea;
(
  node["amenity"="bar"](area.searchArea);
  way["amenity"="bar"](area.searchArea);
  node["amenity"="nightclub"](area.searchArea);
  way["amenity"="nightclub"](area.searchArea);
  node["craft"="brewery"](area.searchArea);
  node["amenity"="wine_bar"](area.searchArea);
  node["amenity"="marketplace"](area.searchArea);
  way["amenity"="marketplace"](area.searchArea);
);
out body;
>;
out skel qt;
```
 
</details>


### Tech Stack

| Layer | Tool | Notes |
|---|---|---|
| Data extraction | Python + Overpass API | Queries OpenStreetMap POIs for Berlin |
| ETL orchestration | GitHub Actions | Scheduled extraction runs automatically |
| Storage | Parquet | Faster to query than CSV |
| Query engine | DuckDB | Runs SQL directly on Parquet files inside Streamlit |
| Frontend | Streamlit + Folium | Interactive map with persona/district filters |
| Hosting | Streamlit Cloud | Free tier |

### Pipeline
 
```
1. Extract — Python calls Overpass API → fetches Berlin POIs by category
        │
        ▼
2. Transform — cleans and normalizes the raw JSON (tags, coordinates, nulls)
        │
        ▼
3. Load — saves output as berlin_pois.parquet to the GitHub repo
        │
        ▼
4. App (Streamlit)
   User selects persona + district
        │
        ▼
   DuckDB: SELECT * FROM berlin_pois WHERE district_name='Mitte' AND subcategory IN ('Restaurants','Cafes')
        │
        ▼
   Folium renders filtered pins on the Berlin map
```
 

---

## UI Design (karina/design branch)

This branch replaces the original sidebar-based layout with a fullscreen map and a compact top bar. The visual theme shifts from yellow to a **charcoal + muted amber** palette.

### Design tokens

| Token | Value | Role |
|---|---|---|
| `INK` | `#23211D` | Primary text, active buttons |
| `PAPER` | `#FAF8F3` | Background, panel surfaces |
| `ACCENT` | `#B5863C` | Muted amber — bee colour |
| `LINE` | `#E7E2D7` | Borders |
| `MUTED` | `#8C8578` | Secondary text |

Category pins on the map each use a distinct muted colour (amber, purple, steel blue, sage green, grey) rendered as small hexagon markers matching the app's honeycomb motif.

---

## Filter Structure

Filters are split across the **top bar** (primary) and the **Filters popover** (secondary refinements).

### Top bar (always visible)

```
beePOV  |  District ▾  |  Search…  |  📍  |  Food  Night  Culture  Nature  Transit  |  Filters
```

| Control | Behaviour |
|---|---|
| District dropdown | Selects one of 6 Berlin districts (or City View) and recenters the map |
| Search field | Typing a district name jumps the map to it |
| 📍 locate button | Requests browser geolocation and recenters the map on the user |
| Honeycomb buttons (Food · Night · Culture · Nature · Transit) | Toggle-style; active = filled dark, inactive = outline. Multiple can be on at once |
| Filters popover | Opens a panel with Select/Clear all, Refine toggles, and Shuffle |

### Subcategory row (appears on category toggle)

When one or more category buttons are active, a row of subcategory checkboxes appears directly under the top bar — one column per active parent:

| Category | Subcategories |
|---|---|
| Food & Drink | Restaurants · Cafes · Bakeries & Street Food |
| Nightlife | Bars & Pubs · Clubs · Breweries & Wine Bars |
| Culture | Museums & Galleries · Landmarks · Churches |
| Nature | Parks & Gardens · Lakes · Hiking & Trails |

All subcategories are checked by default; unchecking one removes those POIs from the query.

### Filters popover (secondary refinements)

- **Select all / Clear all** categories  
- **Refine results:** Free entry · Wheelchair accessible · Vegan friendly · LGBTQ+ friendly  
- **Max places** slider (5–50, default 15)  
- **Min 🐝 rating** slider (0–5)  
- **Shuffle results** — randomises the POI selection

### User flow

```
Select district (dropdown or map click)
        │
        ▼
Toggle one or more category buttons
        │
        ▼
Subcategory row appears → uncheck to narrow (optional)
        │
        ▼
Map loads pins for the active combination
        │
        ▼
Click a pin → slide-in rating panel appears on the right
        │
        ▼
Tap a bee (1–5) to rate the place
```

### Map behaviour

- The map viewport **persists** — panning or zooming does not reset on the next interaction.
- Clicking a district polygon on the map selects it without recentering (the user's current view is kept).
- Choosing a district from the dropdown or searching intentionally recenters the map on that district.
- Clicking **📍** recenters the map on the user's GPS position (zoom 15). Subsequent reruns preserve that view until the user navigates elsewhere.

### Right-hand panel

| Trigger | Panel shown |
|---|---|
| No pins loaded | Nothing |
| Pins loaded, no marker clicked | **Overview**: Visible / Rated / Average stats + Top 5 bee-rated places |
| Marker clicked | **Place panel**: category tag, name, district, bee meter score, 1–5 bee rating links |
| ✕ button or `?close_panel=1` | Panel dismisses, view returns to Overview |

---

### Usage

The app is hosted on Streamlit Cloud. See `Deploy in Streamlit Cloud.md` for deployment instructions.

To run locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Requires `data/berlin_pois.parquet` and `data/layer_districts.geojson` to be present. Place ratings are stored locally in `data/bee_ratings.json` (created automatically on first rating).

