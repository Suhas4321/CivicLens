# Bengaluru South ward geography research

**Status:** research finding, not an implementation specification  
**Retrieved on:** 2026-09-15  
**Geographic target:** Bengaluru South City Corporation, 72 wards  
**Provenance rule:** any boundary adopted by CivicLens is **Derived Public**, never
authoritative.

## Executive finding

The initial concern was justified when it was raised, but the public-data position has
changed since September 2025.

An authoritative **legal and cartographic definition** of the 72 Bengaluru South wards now
exists. The Government of Karnataka issued the final South delimitation as Notification
No. UDD 293 BBS 2025 on 19 November 2025. It subsequently issued amendments on
1 December and 18 December 2025. The current Greater Bengaluru Authority (GBA) site also
publishes corporation delimitation-map downloads and a point-based "Know Your New City
Corporation" service.

What was **not found** is an authoritative, government-published, explicitly licensed,
machine-readable GIS package for the corrected 72 South wards. The official material is
published primarily as maps, notification schedules and interactive services. Karnataka
GIS still exposes the superseded 198- and 225-ward BBMP layers, not a verified 369-ward GBA
layer.

Two current machine-readable redistributions do exist:

- OpenCity publishes KML for all 369 final GBA wards. Its catalogue identifies GBA as the
  source and declares the dataset "Other (Public Domain)", but OpenCity/Oorvani is the
  redistributor, not the authoritative boundary publisher. Its latest KML is dated
  8 December 2025 and says it incorporates the 1 December name changes; it does not say
  that it incorporates the 18 December amendment.
- OpenStreetMap (OSM) contains 369 `admin_level=10` ward relations and the five new
  corporation relations at `admin_level=8`. A spatial query against the Bengaluru South
  corporation relation returns exactly 72 ward relations. The import changeset cites the
  OpenCity dataset. OSM is legally reusable under ODbL 1.0 with attribution, but it is a
  community-maintained derivative and is not authoritative. Seventy-one of the 72 South
  ward relations still carry a 26 November 2025 edit date.

**Recommendation:** for the prototype, snapshot the 72 OSM ward polygons and use strict
point-in-polygon assignment. Label every assignment **Derived Public — OSM/OpenCity/GBA
lineage — medium confidence — not an official ward determination**. If a pin falls in no
polygon, on a shared edge, or in more than one polygon, do not guess: leave the ward unknown
and group/display the report by citizen-confirmed locality plus road. This gives the
ward-first dashboard useful current boundaries without presenting community geometry as a
government fact.

Before any production or government use, obtain either a GBA/Urban Development Department
GIS export with explicit reuse terms or written confirmation that the final geometry may be
reused, and reconcile it against both December amendments.

## Scope and method

This was a public-web and public-API review, not a cadastral or legal survey. It checked:

- current GBA and Bengaluru South government pages;
- the final notification, amendments and election material;
- Karnataka GIS REST services, Karnataka Open Data and Bengaluru Open Data;
- historical BBMP notifications and redistributed layers;
- current OSM relations and their import changeset;
- OpenCity, DataMeet, Bharatlas, Samashti KGIS and an IISc/academic catalogue.

Counts reported as "verified" were read from the source or counted from the public
machine-readable layer on 2026-09-15. No ward name is reproduced here unless it was visible
in a cited source. A catalogue's licence label is reported exactly as declared; that does
not independently prove that the redistributor owned every right needed to apply it.

## Timeline: 198, 243, 225, 368 and 369 are different schemes

The phrase "the 2023 draft 243 wards" combines two different delimitation exercises.

| Date / period | Scheme | What happened | Status in 2026 |
|---|---:|---|---|
| 2009–2023 operational frame | 198 | The elected BBMP geography used the familiar 198 wards. Karnataka GIS still exposes this layer. | Superseded; historical only. |
| 23 June / 14 July 2022 | 243 | The State published a draft and then finalised 243 BBMP wards under Notification No. UDD 66 BBS 2022. | Superseded; it was not the final 2023 scheme. |
| 18 August / 25 September 2023 | 225 | A new draft and final delimitation reduced/replaced the 243 scheme with 225 BBMP wards. | Superseded by the GBA restructuring. |
| 30 September 2025 | 368 | Draft GBA delimitation across five corporations. | Draft only. |
| 19 November 2025 | 369 | Final GBA delimitation. Bengaluru West increased from 111 to 112; the other corporation counts stayed the same. | Current scheme, subject to later amendments. |
| 1 and 18 December 2025 | 369 | Amendments to the November notifications; the South ward count remained 72. | Part of the current legal record. |

The 243 wards were therefore **not simply partitioned among the five corporations**. They
were superseded first by the 225-ward BBMP scheme and then by a fresh GBA delimitation with
ward numbering scoped to each new corporation.

### Five-corporation partition

| Corporation | Draft, 30 Sep 2025 | Final, 19 Nov 2025 |
|---|---:|---:|
| Bengaluru Central | 63 | 63 |
| Bengaluru East | 50 | 50 |
| Bengaluru North | 72 | 72 |
| Bengaluru South | 72 | 72 |
| Bengaluru West | 111 | 112 |
| **Total** | **368** | **369** |

The final counts above were also independently counted from OpenCity's 8 December KML.

## Candidate-source register

Confidence describes confidence in the stated count/vintage and suitability for the noted
purpose, not a claim that a non-government geometry is authoritative.
**Every source row below was retrieved on 2026-09-15.** "Source date" is separately
recorded because publication vintage and research retrieval date are not interchangeable.

### A. Current government and legal sources

| Candidate and exact URL | Publisher | Source date | Format | Licence / reuse position | Vintage and wards | Confidence and use |
|---|---|---|---|---|---|---|
| [GBA city-corporation delimitation maps](https://www.bbmp.gov.in/maps/) | Greater Bengaluru Authority, Government of Karnataka | Current page; map notification lineage is 2025 | HTML index with downloadable map documents | No explicit dataset reuse licence located on the page | Post-restructuring; five corporations, final total 369; South 72 | **High** for official cartography; not a verified bulk GIS export |
| [Final Bengaluru South notification, UDD 293 BBS 2025](https://data.opencity.in/dataset/863209cb-4ced-4f51-b5c5-156939c50922/resource/bb2a742b-5aff-49bf-91a4-d379d48645a5/download/fabca1e3-1a87-4f17-beb5-d8558acabb8d.pdf) | Government of Karnataka, Urban Development Department; copy redistributed by OpenCity | 19 Nov 2025 | PDF gazette; Kannada and English schedules | No explicit licence located in the government PDF. The containing OpenCity dataset declares "Other (Public Domain)"; that is a catalogue assertion by the redistributor. | Post-restructuring; South 72 | **High** for the legal ward schedules/count; not directly usable for point-in-polygon |
| [South amendment / corrigendum](https://data.opencity.in/dataset/863209cb-4ced-4f51-b5c5-156939c50922/resource/90602667-d8c7-4e7f-9990-fb2537eb0215/download/9481.pdf) | Government of Karnataka, Urban Development Department; copy redistributed by OpenCity | 1 Dec 2025 | PDF gazette | Same position as the final notification above | Post-restructuring; South remains 72; ward-name corrections | **High** for the corrections it contains |
| [8 Jan 2026 South reservation notification](https://data.opencity.in/dataset/e6356d29-ce41-4bc7-8292-bbd790070e14/resource/fd53b533-7566-4973-96fa-84ffa5abf380/download/9724.pdf) | Government of Karnataka, Urban Development Department; copy redistributed by OpenCity | 8 Jan 2026 | PDF gazette | No explicit government-document licence located | Post-restructuring; explicitly records the 19 Nov delimitation and both 1 Dec and 18 Dec amendments; South 72 | **High** as evidence that both amendments form the legal chain; not geometry |
| [Know Your New Corporation](https://bbmp.gov.in/KnowYourNewCorporation/) | Greater Bengaluru Authority | Current service retrieved 15 Sep 2026 | Interactive JavaScript location lookup | No explicit data/API licence located | Post-restructuring; current GBA scheme | **High** as a manual point-checking reference; no verified bulk export or stable public API contract |
| [GBA GIS Viewer](https://www.bbmp.gov.in/gisviewer/) | Greater Bengaluru Authority | Current service retrieved 15 Sep 2026 | Interactive web GIS | No explicit download licence or documented ward API located | Post-restructuring status is not sufficiently described in discoverable metadata | **Medium-low** until its ward layer, vintage and export terms are verified |
| [GBA 2026 voter service portal](https://gba.karnataka.gov.in/electoral2026/) | GBA Department of Information Technology; rolls identify the Karnataka State Election Commission | 2026 election cycle | Interactive lookup and ward/polling-station PDF rolls | No boundary-data licence located | Post-restructuring; elections/rolls operate on 369 wards, South 72 | **High** for operational ward identity; **not a boundary source** |
| [Bengaluru South corporation site](https://bengalurusouth.karnataka.gov.in/) | Bengaluru South City Corporation, Government of Karnataka | Current page retrieved 15 Sep 2026 | HTML portal | General website terms; no machine boundary dataset licence found | Post-restructuring; links to ward delimitation and GIS services | **High** for institutional status, **low** as a geometry source |

The Election Commission of India delimitation pages concern parliamentary/assembly
delimitation, not Bengaluru municipal ward polygons. Municipal ward delimitation here was
notified by the Karnataka Urban Development Department under the Greater Bengaluru
Governance Act. The Karnataka State Election Commission uses the resulting wards for local
electoral rolls and elections; its role does not turn the electoral-roll PDFs into a GIS
boundary dataset.

### B. Karnataka GIS and open-data portals

| Candidate and exact URL | Publisher | Source date | Format | Licence / reuse position | Vintage and wards | Confidence and use |
|---|---|---|---|---|---|---|
| [KGIS `BBMP_Ward` layer](https://kgis.ksrsac.in/kgismaps2/rest/services/BBMP/BBMP_Ward/MapServer/0) | Karnataka State Remote Sensing Applications Centre (KSRSAC) | No layer date exposed | Esri REST polygon feature layer; query supports JSON, GeoJSON and PBF | Service `copyrightText` is empty and no layer-specific licence was located | Pre-restructuring; query count verified as 198 | **High** for the old count and geometry availability; **not legally cleared** for reuse by absence of a stated licence |
| [KGIS `BBMP_WardNew` layer](https://kgis.ksrsac.in/kgismaps2/rest/services/BBMP/BBMP_WardNew/MapServer/0) | KSRSAC | No layer date exposed | Esri REST polygon feature layer; query supports JSON, GeoJSON and PBF | Service `copyrightText` is empty and no layer-specific licence was located | Pre-restructuring; query count verified as 225 | **High** for the 2023 count and geometry availability; superseded and not licence-cleared |
| [Karnataka Open Data Portal](https://karnataka.data.gov.in/) | Government of Karnataka / NIC | Portal current on retrieval date | Dataset catalogue and APIs | Portal datasets use their individual licence metadata, commonly Government Open Data Licence – India | No Bengaluru South/GBA 72-ward boundary dataset was located in portal search | **High** confidence in the documented negative as of retrieval; re-check before implementation |
| [Bengaluru Open Data Portal — BBMP group](https://opendata.benscl.com/?q=group%2Fbruhat-bengaluru-mahanagara-palike) | Bengaluru Smart City Limited | Portal current on retrieval date | Dataset catalogue | Licence varies by data package; no applicable ward-boundary package licence was found | No current GBA ward-boundary package surfaced | **Medium** confidence in the negative because portal indexing is inconsistent |

The [Government Open Data Licence – India](https://karnataka.data.gov.in/godl) applies to
datasets actually published under it. It should not be assumed to cover a map or REST layer
on a different government site when that item carries no licence metadata.

### C. Historical BBMP sources and redistributions

| Candidate and exact URL | Publisher | Source date | Format | Licence / reuse position | Vintage and wards | Confidence and use |
|---|---|---|---|---|---|---|
| [Official notification of 243 BBMP wards](https://bbmp.gov.in/ucc_file/UDD-Notification-of-243-Wards.pdf) | Government of Karnataka / BBMP | Draft 23 Jun 2022; final 14 Jul 2022 | PDF notification and textual schedules | No explicit reuse licence located in the PDF | Pre-restructuring; 243 | **High** for the historical legal scheme; no machine geometry |
| [BBMP election information page](https://site.bbmp.gov.in/Election2.html) | BBMP | 2023 page | HTML with gazette and "BBMP Ward Boundaries-243" links | No explicit boundary-data licence located | Pre-restructuring; references 243 | **Medium** as a historical index; links/vintage must be checked before reuse |
| [OpenCity BBMP Wards Delimitation 2023](https://data.opencity.in/dataset/bbmp-wards-delimitation-2023) | OpenCity, a programme of Oorvani; catalogue source field says BBMP | Dataset created 23 Aug 2023; last updated 27 Nov 2025 | Final and proposed KML plus notification/map PDFs | Catalogue declares "Other (Public Domain)" | Pre-restructuring; proposed 225 and final 225 | **Medium-high** as a reproducible historical derivative; not authoritative publication |
| [OpenCity BBMP Ward Information](https://data.opencity.in/dataset/bbmp-ward-information) | OpenCity / Oorvani | Dataset created 11 Apr 2022; last updated 27 Nov 2025 | KML and CSV resources for 198, 243 and 225 schemes | **No License Provided** on this catalogue record | Pre-restructuring; 198, 243 and 225 | **Medium** for research comparison; do not ingest from this record without permission/clarification |
| [DataMeet Bengaluru folder](https://github.com/datameet/Municipal_Spatial_Data/tree/master/Bangalore) | DataMeet India community | Repository last materially updated before GBA restructuring | GeoJSON and KML | Repository declares CC BY 4.0; attribution required | Pre-restructuring; [`BBMP_oldWards.geojson`](https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Bangalore/BBMP_oldWards.geojson) has 198 features and [`BBMP.geojson`](https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Bangalore/BBMP.geojson) has 243 | **High** for lawful historical prototype reuse; wrong scheme for current ward assignment |

The 2023 final 225-ward process is described by the 2023 notification resources above.
Contemporary reporting also records a draft of 225 wards in August and final notification
on 25 September 2023. It should not be described as a "2023 draft 243" scheme.

### D. Current third-party, OSM and academic candidates

| Candidate and exact URL | Publisher | Source date | Format | Licence / reuse position | Vintage and wards | Confidence and use |
|---|---|---|---|---|---|---|
| [OpenCity GBA Wards Delimitation 2025](https://data.opencity.in/dataset/gba-wards-delimitation-2025) and [8 Dec KML](https://data.opencity.in/dataset/863209cb-4ced-4f51-b5c5-156939c50922/resource/9013d656-8051-4e2d-9648-46efd0d86d3d/download/gba-369-wards-december-2025.kml) | OpenCity / Oorvani; catalogue source says GBA | Final KML 25 Nov 2025; revised KML 8 Dec 2025 | KML; additional PDF/CSV resources | Catalogue declares "Other (Public Domain)" but supplies no specific public-domain instrument in the record | Post-restructuring; 369 total and 72 South, verified by parsing; revised KML says it includes 1 Dec name changes | **Medium-high** for prototype geometry; **not authoritative** and 18 Dec incorporation is unconfirmed |
| [OSM Bengaluru South corporation relation 19369534](https://www.openstreetmap.org/relation/19369534), [GBA ward import changeset 175125404](https://www.openstreetmap.org/changeset/175125404) | OpenStreetMap contributors / OpenStreetMap Foundation | Ward import 25 Nov 2025; most South relations last edited 26 Nov 2025; live data retrieved 15 Sep 2026 | OSM relations; XML API/Overpass extracts can be converted to GeoJSON | ODbL 1.0; attribution and database share-alike obligations apply | Post-restructuring; live query found 369 ward relations, exactly 72 within South | **Medium-high** for a versioned prototype snapshot; clear licence, complete current count, but community-derived and mostly predates both December amendments |
| [Bharatlas Bengaluru GBA ward layer](https://bharatlas.com/view/wards_bengaluru_gba) | Bharatlas | Source snapshot 26 May 2026 | Parquet, GeoJSON, KML and PMTiles | Page declares ODbL 1.0 and attributes OpenCity | Post-restructuring; 369 | **Medium-low**: useful conversions, but an additional derivative hop with no added authority |
| [Samashti KGIS redistribution](https://github.com/samashti/KGIS) | Nikhil S. Hubballi / Samashti | Repository current on retrieval date; underlying layer date not stated | Zipped GeoPackage and extraction scripts | Repository declares CC0 1.0; upstream KGIS service does not expose a clear layer licence, so the downstream declaration does not resolve upstream rights | Statewide town wards; no verified post-GBA 369/South-72 version | **Low** for this purpose; do not use as the current South boundary source |
| [IISc Bangalore Urban Information System](https://wgbis.ces.iisc.ac.in/sdss/BUiS/) | Energy and Wetlands Research Group, Centre for Ecological Sciences, IISc | Launched 22 Jan 2024; underlying ward studies use the 198-ward frame | Interactive spatial decision-support system | No downloadable ward-layer licence located | Pre-restructuring; 198-ward research frame | **High** as academic context, **low** as a reusable current boundary source |
| [NYU/Princeton Bangalore ward boundaries and census information](https://geo.nyu.edu/catalog/princeton-bg257j49j) | Creator ML Infomap; provider Princeton; catalogue hosted by NYU | Temporal coverage 2011/2016 | Shapefile/WMS catalogue record | Access Rights: **Restricted** | Pre-restructuring; historical ward layer | **High** that it is unsuitable for current or open reuse |

## OSM assessment in detail

OSM is no longer limited to the old 225 wards.

On 2026-09-15, the public OSM API showed:

- [relation `7902476`](https://www.openstreetmap.org/relation/7902476): Bengaluru/GBA,
  `admin_level=7`, with five corporation subareas;
- relation `19369534`: Bengaluru South City Corporation, `admin_level=8`;
- 369 relations in the Bengaluru bounding box tagged `admin_level=10`,
  `local_authority:IN=ward` and a `ward` number;
- exactly 72 such relations spatially inside relation `19369534`.

The original import changeset, `175125404`, says that it added the new GBA wards, removed
the old BBMP ward/zone relations and used this source:

`https://data.opencity.in/dataset/gba-wards-delimitation-2025`

The individual relations do not carry a `source` tag. Of the 72 South relations, 71 were
last edited on 26 November 2025 and one on 3 April 2026. This is evidence of a coherent,
current-scheme import, but not evidence that the 1 and 18 December corrections were fully
reconciled.

OSM's licence is explicit: [OpenStreetMap data is ODbL
1.0](https://www.openstreetmap.org/copyright). CivicLens must display visible attribution
such as **© OpenStreetMap contributors**, link to the copyright/licence page, and comply
with ODbL obligations for any distributed derivative database. OSM must never be labelled
or styled as an official GBA boundary source.

## Design options if an authoritative machine boundary is unavailable

### Option 1 — OSM point-in-polygon, with a locality-and-road fallback (recommended)

Snapshot the 72 `admin_level=10` OSM relations spatially contained by South relation
`19369534`. Assign a citizen-confirmed pin only when it is contained by exactly one valid
polygon.

**Benefits:** current 72-ward scheme; complete coverage; machine-readable; ODbL provides a
clear reuse route; repeatable and testable.  
**Costs/risks:** derived from OpenCity rather than supplied by GBA as GIS; most relation
versions predate the December amendments; ODbL attribution/share-alike obligations; border
points require an explicit unknown state.

### Option 2 — OpenCity's 8 December KML directly

Use the South subset of the 369-feature KML and preserve the OpenCity/GBA lineage.

**Benefits:** one derivative hop closer to the listed GBA source; includes the 1 December
name changes and population attributes.  
**Costs/risks:** "Other (Public Domain)" is a catalogue label rather than a named licence
instrument; no stated incorporation of the 18 December amendment; still not authoritative.

### Option 3 — old BBMP boundaries with a pre-restructuring label

Use the licence-clear DataMeet 198- or 243-feature layer, or the KGIS 225 layer if reuse
permission is clarified.

**Benefits:** stable historical files and, for DataMeet, explicit CC BY 4.0 terms.  
**Costs/risks:** assigns reports to a ward scheme that no longer represents Bengaluru South;
misleading even with a label; old and new ward identifiers are not interchangeable. This
should be a historical comparison view only, never the default current grouping.

### Option 4 — defer wards; group by locality plus road

Keep the current citizen-confirmed pin but organise the dashboard by locality and road
until an authoritative GIS export is obtained.

**Benefits:** avoids false administrative precision and avoids boundary-licence questions.  
**Costs/risks:** locality polygons/names are inconsistent and can resolve to adjacent
suburbs; officers lose the requested ward-first view. This remains the correct fallback for
ambiguous and out-of-coverage points.

## Recommended assignment contract

For the prototype only:

1. Freeze a dated OSM extract of the 72 South relations; do not query OSM or Overpass on the
   live request path.
2. Record the extract hash, OSM relation IDs and versions, import changeset, source lineage,
   retrieval date and ODbL licence in a manifest.
3. Validate that the snapshot has 72 valid polygons, no unexplained overlaps/gaps, unique
   `(corporation, ward_number)` identities and the expected South corporation envelope.
4. Compare ward numbers/names against the 19 November notification, 1 December corrigendum
   and the later government document that confirms the 18 December amendment. Any
   unresolved discrepancy lowers the relevant ward to `low` confidence or `unknown`.
5. Use the citizen-confirmed pin as the authoritative report location. EXIF, OSM locality
   centroids and geocoder display names must not silently move it.
6. Run containment against the frozen polygon snapshot:
   - exactly one interior match: attach the derived ward;
   - zero matches: `ward_unknown`;
   - more than one match or a shared-boundary hit: `ward_ambiguous` and human review.
7. Never assign the nearest ward or nearest centroid. In unknown/ambiguous cases, retain
   locality plus road grouping.
8. Display a visible provenance label and OSM attribution wherever ward grouping or a ward
   map is rendered.

Minimum stored provenance for a derived assignment:

```text
classification: Derived Public
source: OpenStreetMap relations, derived from OpenCity GBA Wards Delimitation 2025
retrieved_on: 2026-09-15
licence: ODbL-1.0
confidence: medium
authoritative: false
boundary_version: <snapshot identifier and hash>
assignment_method: citizen-confirmed pin within exactly one polygon
```

Suggested citizen/officer wording:

> Ward shown from a derived public boundary snapshot (OpenStreetMap/OpenCity, retrieved
> 15 Sep 2026). It is not an official ward determination.

## Decision and follow-up

The dashboard may proceed with a **derived ward view**, not an authoritative ward view. OSM
is the recommended geometry source because it contains the complete current scheme and has
clear ODbL terms. Locality plus road remains the fallback, not a competing source of ward
truth.

Before production use, request from GBA/Urban Development Department:

- the corrected 369-ward and South-72 GIS package (GeoJSON, KML, GeoPackage or shapefile);
- a version/effective date tied to the 19 November notification and both December
  amendments;
- coordinate reference system and topology notes;
- explicit licence/reuse and attribution terms; and
- a stable point-to-ward or download API, if one exists.

Until those are supplied, CivicLens must preserve `source`, `retrieved_on`, `confidence`,
licence and `authoritative=false` on every boundary and assignment derived from it.
