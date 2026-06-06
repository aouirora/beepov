# BeePOV Map
> A map of Berlin designed to reduce cognitive overload through.
---

## Table of Contents

- [Background](#background)
- [User Research](#user-research)
- [Mission Statement](#mission-statement)
- [Tech](#tech)
- [Filter Structure](#filter-structure)

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
**Bio:** A Berlin local who spends her free time hunting for authentic spots, cafés, parks, and cultural places that actually match her taste, not just 
whatever shows up first on the map.  
**Tools she uses:** Mara uses Google Maps multiple times a day, and uses Instagram and TikTok for recommendations.  
**What she likes:**  
-  Cafes, museums, parks, cultural spots
-  She trusts friends and social medias over generic lists; typically needs 3–4 mentions before visiting a place
-  Craves for local hidden gems, not the same tourist spots everyone else visits 
**Frustrations:** 
- Finding places that match her interests
- Planning efficient routes
- Tourist recommendations feel repetitive


>*Mara: "I'll spend ages deciding where to go — and half the time the place isn't what the photos promised."*

---

## Mission Statement  
> *To be added.*

---

## Tech

### Data
> *TBD*
> 
| Category | Source | Format |
|---|---|---|
| District boundaries | Berlin Open Data Portal — daten.odis-berlin.de | GeoJSON |
| Nightlife & Food & Drink | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Culture & Heritage | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Nature & Outdoors | Overpass Turbo (OpenStreetMap) | GeoJSON |
| Public transport stops | VBB Open Data — unternehmen.vbb.de | CSV |
| Hotels & tourism | Berlin Open Data — daten.berlin.de | XLS |
| Street parades & markets | Berlin Open Data — daten.berlin.de | GeoJSON |

Overpass queries use standard OSM tags (`amenity`, `tourism`, `leisure`, `natural`, `historic`, `craft`) to extract Berlin POIs by category, all scoped to the Berlin administrative boundary via `{{geocodeArea:Berlin}}`.

### Tech Stack
> *TBD*
>
> 
| Layer | Tool | Rationale |
|---|---|---|
| Data Source | Overpass API (OpenStreetMap) + Berlin Open Data Portal | Free, comprehensive, well-maintained |
| ETL Pipeline | Python | Flexible; handles JSON, GeoJSON, CSV, and XLS |
| Storage | Parquet files | Faster to query than CSV at our data scale |
| Query Engine | DuckDB | Runs SQL directly on Parquet files inside Streamlit; ideal for our scale |
| Frontend | Streamlit + Folium / Leaflet | Rapid prototyping; free cloud hosting |
| Hosting | Streamlit Community Cloud | Free tier; accessible via mobile browser |

### Pipeline
> *TBD*
```
Extract  →  Transform  →  Load  →  App
```

**Step 1 — Extract** (GitHub Actions):
A Python script calls the Overpass API and downloads Berlin POIs as GeoJSON files.

**Step 2 — Transform**:
Python cleans and normalises the raw data. OSM tags are mapped to BeePOVMap's filter categories and district fields are standardised.

**Step 3 — Load**:
Output is saved as `berlin_pois.parquet` in the GitHub repository, ready for the app to query.

**Step 4 — App** (Streamlit):
- User selects a district and category (e.g., *Mitte* + *Food & Drink*)
- DuckDB executes: `SELECT * FROM data WHERE category = 'Food' AND district = 'Mitte'`
- Folium renders the resulting pins on the interactive map

---

## Filter Structure

BeePOVMap uses a three-step hierarchical filter system. Each step progressively narrows the result set before the map renders.

```
STEP 1: District  (multi-select)
├── Mitte              ★ Brandenburg Gate, Museum Island, Alexanderplatz always pinned
├── Kreuzberg / Friedrichshain
├── Prenzlauer Berg
├── Charlottenburg
├── Neukölln
└── Schöneberg
    → Districts are colour-coded on the map
    → Selecting a district narrows visible markers before categories are applied

STEP 2: Category  (multi-select)
├── Food & Drink                                             248 places
│   ├── Restaurants
│   ├── Cafés
│   └── Bakeries & Street Food
├── Nightlife                                                 89 places
│   ├── Bars & Pubs
│   ├── Clubs
│   └── Breweries & Wine Bars
├── Culture & Heritage                                        61 places
│   ├── Museums & Galleries
│   ├── Landmarks
│   └── Churches
└── Nature & Outdoors                                         44 places
    ├── Parks & Gardens
    ├── Lakes
    └── Hiking & Trails
    → Sub-categories appear inline only when their parent category is selected
    → Map updates dynamically after each selection
    → Multi-select is intentional: users can combine e.g. Food + Culture

STEP 3 (OPTIONAL): Refinements
Always visible:
    ☐ Open Now
    ☐ Open Late (after 22:00)
    ☐ Near Public Transport  (≤ 5 min walk)
    ☐ Free / Budget-friendly  (€)
    ☐ Wheelchair Accessible
    ☐ LGBTQ+ / FLINTA Friendly
Shown only when Food & Drink is selected:
    ☐ Vegan / Vegetarian Friendly
    ☐ Outdoor Seating
```

### User Flow

```
Pick district(s)  →  Pick category/ies  →  Select sub-options  →  Refine (optional)  →  Map result
```






