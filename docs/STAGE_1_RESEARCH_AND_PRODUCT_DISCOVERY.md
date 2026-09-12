# CivicLens AI — Stage 1 Research & Product Discovery

## Executive conclusion

CivicLens is directionally well matched to Track 1, but the current concept is not differentiated enough to be competitive on its own. Multilingual voice/text/photo intake, AI classification, duplicate filtering, hotspot maps, and official dashboards were all represented in the first edition's top governance projects. CPGRAMS already advertises AI-based urgent-case flagging, spam/repeat detection, semantic summarisation, topic clustering, and spatiotemporal analysis. A polished implementation of the current pipeline would therefore demonstrate competent execution, but judges could reasonably ask, “What is new here?”

The recommended product pivot is narrow but important:

> **CivicLens is an explainable civic needs-to-project decision-intelligence layer. It turns multilingual citizen signals into deduplicated need patterns, combines them with public service-gap, demographic, and existing-investment data, and produces auditable project candidates for human decision-makers.**

Citizen reporting remains the front door, but no longer the core innovation. The central demo should prove a transition that existing complaint portals do not usually make visible:

> repeated service incidents → evidence of a systemic need → equity-aware priority → feasible project candidate → recorded human decision → public outcome

This positioning is closer to the official Track 1 challenge, which explicitly asks teams to combine citizen feedback with demographic data, infrastructure indices, and public investment plans, then surface demand hotspots and recommend high-priority development projects. It is also meaningfully more defensible than a generic grievance dashboard.

---

## 1. Verified hackathon findings

### 1.1 Current event and timeline

**Verified — official Hack2Skill event page, accessed 11 September 2026**

- “Build with AI: Code for Communities — Second Edition” is a free, hybrid Google Cloud hackathon open to developers, AI/ML practitioners, product thinkers, freelancers, students, professionals, and startups across India.
- Team size is one to four members; solo participation is allowed.
- Registration and prototype submission close on **30 September 2026**.
- Prototype evaluation is listed for 1–15 October; the Top 20 announcement for 16 October; and a virtual Demo Day for 23 October. The in-person Demo Day date and venue are still TBA.
- The total cash prize pool is **₹10 lakh**.
- The page says top teams will receive Google Cloud credits. It separately instructs participants to confirm Google AI Studio and Vertex AI credit details with organizers; pre-submission credits should therefore not be assumed.

The official page is the authoritative source for these current details.[^1]

### 1.2 Track 1 wording matters

**Verified — official Track 1 brief**

Track 1 is “AI for Digital Public Infrastructure & Governance,” under the theme of Innovation. The problem is not framed merely as municipal complaint handling. It is the fragmentation of citizen development requests and the failure to align them with national infrastructure priorities, causing misaligned spending and unaddressed infrastructure gaps.

The challenge asks for a scalable, multilingual AI platform, designed as a Digital Public Good, that:

- aggregates citizen development requests through voice, text, and messaging apps;
- works across diverse linguistic regions;
- analyses citizen feedback together with national demographic data, infrastructure indices, and public investment plans;
- surfaces demand hotspots;
- recommends high-priority development projects to national policymakers; and
- is designed for scale beyond a single city.

**Implication:** CivicLens currently over-indexes on operational municipal incidents—potholes, garbage, streetlights—and under-indexes on development planning. The strongest version must distinguish an isolated service incident from a recurring or structural service gap that may justify a project or policy intervention.

### 1.3 Mandatory build and submission requirements

**Verified — official event page**

The working prototype must demonstrate:

- an end-to-end flow for the core use case;
- meaningful Google AI integration—generative AI, predictive modelling, computer vision, or equivalent;
- real or realistic data, including public datasets, sample data, or APIs when live data is unavailable;
- a design that can scale across Indian states and communities; and
- multilingual or voice support where required by the track.

The submission package is:

1. source code in a public or access-granted GitHub repository;
2. a 3–5 minute working demo video;
3. a 10–12 slide pitch deck;
4. a 2–3 line description; and
5. a live deployed prototype link.[^1]

### 1.4 Judging criteria

**Verified — official event page, in stated weight order**

| Criterion | Weight | Consequence for CivicLens |
|---|---:|---|
| AI / Technical Execution | 25% | Gemini must perform real multimodal/language work in a functioning pipeline; the deterministic engine and failure handling must be visible. |
| Problem–Solution Fit | 20% | The product must address infrastructure planning and high-priority projects, not only complaint resolution. |
| Depth & Reach Across India | 20% | One well-instrumented pilot is acceptable only if geography, taxonomy, language, and data adapters are demonstrably configurable. |
| Deployability & Scalability | 20% | A coherent modular monolith, public URL, seeded demo, audit trail, and realistic integration boundary are more valuable than speculative enterprise architecture. |
| Impact Potential | 15% | The story should quantify who benefits and how the decision process improves, without claiming unverified real-world impact. |

### 1.5 Expected Google technology

**Verified**

Google AI integration is mandatory. The official page recommends, but does not require every one of, Gemini API, Google AI Studio, Vertex AI, Gemini multimodal, Cloud Speech-to-Text/Text-to-Speech, Translation API, Dialogflow, Google Maps Platform, BigQuery, Firebase, Cloud Run, Cloud Functions, and public Indian data portals.[^1]

**Recommendation**

Use a small number of Google services where each has a visible role:

- Gemini for multilingual, multimodal, schema-constrained report understanding;
- Gemini Embeddings only if semantic duplicate detection materially improves the evaluation set;
- Google Maps Platform for location capture and the official decision map;
- Cloud Run for the API/processing service; and
- optionally Firebase Authentication for officer identity.

Do not add BigQuery, Vertex pipelines, Dialogflow, Earth Engine, or multiple serverless products solely to increase the Google logo count. Every added service increases setup and live-demo failure surface.

### 1.6 Previous edition and finalists

**Verified with high confidence, but not all details are from an organizer-hosted results page**

- A GDG program lead reported more than 7,000 registrations, more than 1,000 submitted projects, 12 showcased solutions, and 11 sitting MPs at the first edition's Delhi showcase. Several MPs reportedly expressed interest in constituency pilots.[^2]
- GDG India's public description of the first edition says its governance problem was already about turning thousands of citizen requests into evidence-based decisions.[^3]
- A contemporaneous results report names the first-edition governance podium as:
  - **Tech Jays / Praja Svaram** — multilingual voice-first WhatsApp/phone grievance intake, AI classification and verification, analytics for MPs;
  - **Civic Pulse** — Indian-language text, voice, and photo intake, classification, and demand hotspots; and
  - **Nexons / AreaPulse** — AR/WhatsApp reporting, AI spam and duplicate filtering, government SLA dashboards, and predictive weather risk.[^4]

**Not verified:** An official organizer-hosted winners roster was not located. The named podium above should be treated as well-corroborated secondary reporting, not primary-source proof. Announced pilot interest also does not establish that production pilots were completed or successful.

**Competitive implication:** The unmodified CivicLens concept overlaps heavily with all three top governance entries. Multimodal intake, multilingual support, classification, duplicate detection, mapping, and an official dashboard are table stakes, not a winning differentiator.

---

## 2. Comparable systems and what they teach

### 2.1 Indian public grievance systems

| System | Verified capabilities | Pattern worth borrowing | Limit or white space relevant to CivicLens |
|---|---|---|---|
| **CPGRAMS / IGMS 2.0** | Nationwide portal connected to Union ministries/departments and states; trackable IDs, appeals, feedback. IGMS advertises urgent-case flagging, spam/bulk/repeat detection, semantic gist extraction, topic clusters, and spatiotemporal filtering.[^5][^6] | Role-based government workflow; appeal/feedback loop; AI supports triage and root-cause analysis rather than replacing officials. | CivicLens cannot claim clustering or semantic triage as novel. The public material does not show an open, citizen-auditable need-to-investment decision trail; this is a potential differentiation, not a verified deficiency. |
| **Swachhata Platform** | Photo-first geolocated sanitation complaints, automatic municipal routing, push updates, comments, citizen feedback, category SLAs, and mandatory resolution-image evidence.[^7][^8] | Keep intake fast; require proof of resolution; close the loop with the reporter. | Narrow service domain. It optimizes resolution workflow more than cross-sector capital planning. |
| **Karnataka Janaspandana** | Integrated grievance system spanning 41 departments and 270 line departments, phone intake via 1902, Kannada/English interfaces, citizen and department dashboards.[^9] | Assisted/phone intake matters; department ownership is essential. | Its own visible metrics—63.21% on-time disposal and 43.28% positive feedback when accessed—illustrate that disposal is not the same as a satisfactory outcome. |
| **BBMP Sahaaya 2.0** | Unified text/photo/video grievance intake and tracking across BBMP and related Bengaluru agencies; a Karnataka reform report recommends integrating all control-room channels into the app.[^10] | Multi-agency routing and a single operating view are necessary in real deployments. | Another reason not to build CivicLens as a Bengaluru complaint replacement. It should be an intelligence/interoperability layer or a clearly separate planning prototype. |
| **Janaagraha / IChangeMyCity / Public Eye** | Community participation, civic complaints, agency follow-up, traffic-evidence validation, and visible response commitments; Public Eye reports 18 lakh submitted violations and 13.5 lakh booked.[^11] | Community visibility, evidence validity rules, and agency partnership drive use. | Crowd volume alone does not create fair investment priorities. |

### 2.2 International civic technology

| Product | Useful pattern | Relevance |
|---|---|---|
| **SeeClickFix 311 CRM** | Centralizes web/app/SMS/call-taker requests, routes by category/location, merges duplicates, supports escalation, and provides analytics.[^12] | Confirms that duplicate management, routing, maps, and dashboards are established 311 capabilities. |
| **Ushahidi** | Multi-channel crowdsourcing, mapping, workflows, roles, alerts, collections, and export; used across crisis response, elections, public health, and human rights.[^13] | Demonstrates that source diversity, verification, and workflow are more important than a beautiful heatmap alone. |
| **Decidim** | Collects geolocated proposals, compares/merges similar proposals, records official acceptance/rejection, supports voting and participatory budgeting, and tracks project accountability.[^14][^15] | The best conceptual reference for moving from “complaint” to “proposal/result/accountability.” CivicLens should borrow this lifecycle, not try to reproduce the full participation platform. |

### 2.3 Evidence on what fails

Several recurring failure modes are supported by research and public-system evidence:

1. **Administrative closure can replace meaningful participation.** A 2026 Indian urban-grievance study found that systems are often optimized for administrative completion rather than civic participation; nearly half of surveyed respondents believed filing changes nothing, and three quarters of filers did not feel heard.[^16]
2. **Digital complaints do not automatically produce political responsiveness.** Research using Delhi complaint and interview data found weaker political response to e-governance complaints than to complaints delivered through personal relationships.[^17]
3. **Easy-to-fix complaints can crowd out systemic inequity.** A Mumbai study argues that grievance systems may favour minor, programmatically convenient fixes while leaving systemic under-allocation unresolved.[^18]
4. **Report count is not a neutral measure of need.** Digital access, awareness, language, organized campaigns, and repeated submissions all affect volume. Treating raw count as democratic demand would reward high-reporting communities and could hide underserved areas.
5. **Fragmented routing is an operational failure, not only a UI problem.** CPGRAMS, Janaspandana, and Sahaaya all emphasize cross-department connection or integration, showing that a standalone portal with no ownership model has limited real-world value.

### 2.4 Evidence on what succeeds

Patterns with strong practical support are:

- **Multiple channels and assisted access:** web alone is inadequate; phone/voice and operator-assisted entry widen reach.
- **A very short citizen flow:** photo/location-first systems reduce reporting friction.
- **Clear ownership and service workflow:** every accepted case needs an accountable department or official status.
- **Visible feedback and appeal:** ticket status, citizen feedback, and proof of resolution protect trust.
- **Human verification for consequential decisions:** successful systems use AI to triage or surface patterns, then keep official action attributable.
- **Open/configurable structure:** the challenge calls for a Digital Public Good. The DPG Standard includes open licensing, clear ownership, platform independence, documentation, non-PII data extraction, privacy, open standards, security, and harm protections.[^19]

---

## 3. Competitive whitespace

### 3.1 Features that are now table stakes

These are necessary but weak as headline innovation:

- multilingual text and voice submission;
- photo understanding;
- automatic category and severity suggestions;
- translation or language normalization;
- duplicate filtering;
- map markers, clusters, and heatmaps;
- officer dashboards and trend charts;
- status tracking; and
- a generated summary.

### 3.2 Defensible differentiation

The strongest whitespace is the **auditable conversion of citizen evidence into development choices**:

1. **Two-level civic ontology:** classify an input as an operational incident, a development request, or a signal that may become a systemic need after recurrence. A three-day water outage may be operational; repeated outages across a service zone plus low supply coverage may reveal a development need.
2. **Evidence fusion:** combine unique citizen signals with service-gap indicators, population or exposure, known assets, existing works/investments, time trend, and source diversity.
3. **Equity guardrails:** cap the influence of raw volume; normalize where possible; expose low-participation areas; never infer vulnerability from names, language, caste, religion, or imagery. Use only explicit, aggregate, lawfully sourced area indicators.
4. **Decision packets, not AI decrees:** each ranked need should show the evidence, source dates, score components, uncertainties, counter-evidence, similar/existing works, and what human validation is still required.
5. **Project candidates from a constrained catalogue:** recommend intervention types that are allowed for the relevant authority or scheme, rather than asking an LLM to invent projects, costs, or eligibility.
6. **Public accountability trail:** record reviewed/accepted/deferred/rejected decisions with reasons and show a privacy-safe citizen outcome.
7. **Representation health:** show who and which geographies are missing from the signal, not only where reports are numerous.

This is more aligned with the official track and much harder to dismiss as a chatbot or a 311 clone.

---

## 4. Recommended product change

### 4.1 Revised problem statement

Public bodies do not merely lack a place to receive complaints. They lack a transparent way to distinguish isolated incidents from systemic community needs, combine citizen demand with public evidence, avoid over-weighting the loudest communities, and explain why one development intervention should be reviewed before another.

### 4.2 Revised product promise

> CivicLens helps public representatives see which community needs deserve investigation and investment first—and inspect every signal, dataset, rule, and uncertainty behind that recommendation.

### 4.3 Revised core demo object

The hero object should be a **Need / Project Candidate**, not a complaint ticket.

Example:

> **Recurring water-service gap — North Zone**  
> 143 likely unique supporting reports across 4 local areas; 38% four-week growth; high recurrence after prior closures; 28,400 estimated residents in the affected service area; low nearby storage coverage in the demo infrastructure dataset; no overlapping active work found.  
> **Review priority: 87/100 — High**  
> Suggested intervention class: distribution audit + storage/pipe-capacity assessment.  
> Human validation required: utility outage record, engineering survey, scheme eligibility, and cost estimate.

The recommendation is explicitly a review candidate, not an automated spending decision.

### 4.4 A sharper lifecycle

1. A citizen or assisted operator submits a signal by text, voice, and optionally photo/location.
2. Gemini produces a validated structured interpretation and preserves the original evidence.
3. Deterministic geographic/time/category gates find candidate matches; embeddings may refine semantic similarity.
4. The system links exact duplicates to one report record and related reports to a need cluster without deleting evidence.
5. A need cluster is enriched with aggregate area indicators and existing/planned work data.
6. A deterministic, versioned score ranks it for human review; evidence confidence remains a separate dimension.
7. A constrained intervention catalogue yields one or more project candidates and mandatory validation steps.
8. An officer records a decision and reason; citizens receive a privacy-safe status/outcome.

### 4.5 Why this still fits a hackathon MVP

This pivot does not require a nationwide data platform. The MVP can use one real pilot geography, 100–300 clearly labelled synthetic citizen reports, one or two public aggregate datasets, and a small curated catalogue of intervention types. The architecture can expose adapters for other states without pretending those integrations already exist.

---

## 5. AI and technical option findings

### 5.1 Gemini is suitable—but must be bounded

Google's current documentation supports multimodal image understanding and schema-constrained JSON output. It explicitly recommends application-side validation even when output is syntactically structured, because values may still be semantically wrong.[^20][^21] Current Gemini embedding models support semantic similarity, classification, and clustering, including multilingual and multimodal embeddings.[^22]

**Good Gemini responsibilities**

- language identification and normalization while retaining original text;
- transcription/interpretation of short voice reports;
- bounded extraction of category, issue type, described location, temporal clues, impact cues, and visible image evidence;
- contradiction flags between modalities;
- short, evidence-grounded cluster summaries; and
- embeddings for semantic comparison when deterministic candidate selection has already narrowed the search.

**Poor Gemini responsibilities**

- final numeric priority;
- autonomous duplicate merges;
- exact geospatial membership;
- official jurisdiction, eligibility, or budget decisions;
- invented costs, population estimates, infrastructure facts, or government schemes; and
- access control or status transitions.

### 5.2 Embeddings are useful, not automatically required

For 100–300 seeded reports, normalized category + PostGIS distance + time-window gates + token similarity may be sufficient and easier to test. PostGIS `ST_DWithin` supports indexed radius filtering in metres for geography values.[^23]

Recommended experiment:

- build a labelled set of 30–50 “same incident / related need / unrelated” pairs;
- measure the deterministic baseline;
- add Gemini embeddings only if they materially improve cross-language or paraphrase recall without unacceptable false merges;
- retain human review for ambiguous merges.

Embeddings should improve a measurable failure mode, not exist as architecture decoration.

### 5.3 Public data is available but uneven

- data.gov.in hosts government datasets and APIs under the Government Open Data License–India, but granularity, freshness, and API reliability vary.[^24]
- The official Primary Census Abstract available there is Census 2011 data; it is useful for a demo only when prominently labelled with its vintage.[^25]
- MPLADS exposes funds, sector/work counts, work status, and constituency-oriented dashboards. MPs recommend works, while district authorities sanction and execute them. This is relevant to the product's human-decision boundary.[^26][^27]
- NITI Aayog has explicitly recommended linking geolocated assets to grievance redressal, participatory budgeting, transparent works management, and contractor payments, and notes weak citizen participation in urban planning.[^28]

**Recommendation:** use a small, documented snapshot imported into the demo. Do not make the live demonstration depend on an unstable public API. Show source, date, granularity, licence, and whether each value is real, derived, or synthetic.

### 5.4 Infrastructure viability

- Cloud Run is appropriate for a low-traffic prototype because it supports container deployment, IAM controls, automatic scaling, and scale-to-zero; scale-to-zero can introduce cold-start latency, so the demo should warm the service or configure a minimum instance only during judging if budget allows.[^29]
- Cloud SQL supports PostgreSQL vector features, but a continuously provisioned managed database may be unnecessary cost and setup for the MVP.[^30]
- Google Maps Platform is pay-as-you-go with per-SKU free usage caps and quotas. A hackathon map is viable if API restrictions, quotas, and budget alerts are configured.[^31]

**Stage 1 stack recommendation, subject to Stage 3 design:** Next.js frontend, FastAPI modular monolith, PostgreSQL with PostGIS and optional pgvector, Gemini API/Vertex AI, Google Maps, object storage, and Cloud Run. Choose the simplest managed PostgreSQL option that reliably supports PostGIS/pgvector and does not require unconfirmed hackathon credits. A non-Google database does not weaken the entry if Google AI is meaningful and the architecture is coherent.

---

## 6. Privacy, safety, and legitimacy findings

Citizen reports can reveal precise routines, home locations, faces, vehicle plates, voices, political views, health conditions, and allegations about third parties. This is not low-risk demo data.

India notified the Digital Personal Data Protection Rules in November 2025 with phased commencement. The rules require clear, standalone notice describing itemised personal data and specific processing purposes; many substantive provisions have delayed commencement, but the product should be designed to their standard now.[^32] The DPG Standard likewise treats privacy, lawful processing, non-PII data extraction, security, and protection from harm as baseline design requirements.[^19]

**MVP recommendations**

- Allow low-friction anonymous or pseudonymous reporting, but issue a recovery code or optional contact channel for tracking.
- Do not collect Aadhaar, date of birth, or full home address.
- Store the minimum precise coordinate needed for verification; show officials an approximate location by default and never expose reporter identity on aggregate views.
- Strip EXIF metadata after extracting only the fields explicitly needed; do not trust EXIF as proof.
- Blur faces and plates in officer/public thumbnails when feasible; otherwise use controlled demo media and mark automated redaction as post-MVP.
- Separate original evidence from derived AI fields; version every AI analysis and score.
- Never send PII into logs, analytics, prompts beyond the minimum input required, or seed datasets.
- Mark emergency and safety-critical content with explicit off-platform instructions; CivicLens is not an emergency service.
- Use synthetic reports and licensed/public aggregate data for judging. Label synthetic data prominently in the UI and deck.

This is product and architecture guidance, not a legal opinion.

---

## 7. Resource / budget simulator verdict

**Classification: REMOVE from the hackathon MVP.**

The ₹1 crore allocator creates more risk than judging value:

- credible costs require engineering estimates, procurement assumptions, land constraints, scheme eligibility, recurring expenditure, and local rules;
- an optimization output implies authority and accuracy that the prototype cannot support;
- it would distract from the already difficult need-detection and explainability story; and
- Decidim and real participatory-budget systems show that budgeting is a governance process, not merely a numeric allocation widget.

Replace it with a smaller **Decision Packet**:

- ranked need;
- evidence and score breakdown;
- overlapping planned/completed works;
- one to three constrained intervention types;
- information still required;
- rough cost band only if sourced from a curated demo catalogue and clearly labelled indicative; and
- officer disposition: investigate, combine, defer, reject, or nominate for project assessment.

A true resource-allocation scenario tool can be reconsidered post-hackathon once cost and eligibility data are trustworthy.

---

## 8. MVP discipline emerging from Stage 1

### Must have

- a fast multilingual citizen/assisted report flow with text, short voice, optional image, and location;
- Gemini structured extraction with visible original-versus-derived evidence;
- deterministic candidate matching, deduplication, and need clustering;
- one pilot geography with meaningful seeded multilingual data;
- enrichment with at least one aggregate demographic/service-gap dataset and one existing/planned-works dataset or credible demo equivalent;
- a deterministic, versioned priority score with component breakdown and separate confidence;
- an officer command view centred on ranked needs/project candidates;
- an evidence/explainability view with source provenance and uncertainties;
- a recorded human decision/status and a citizen confirmation/status view;
- a live public deployment and scripted demo modes.

### Should have

- semantic embeddings if the labelled evaluation proves value;
- a representation-coverage warning;
- visible duplicate/related-report review controls;
- constrained intervention catalogue;
- filters for geography, category, time, and status; and
- a simple audit/history timeline.

### Optional / post-hackathon

- WhatsApp or telephony integration;
- live government API integration;
- automated face/plate redaction;
- advanced forecasting;
- public participatory voting;
- cross-state federation;
- full DPG certification work; and
- automated scheme matching.

### Remove

- free-form “ask the dashboard” chatbot;
- autonomous AI prioritization;
- budget allocation optimizer;
- real-time streaming architecture;
- microservices, Kafka, Kubernetes, or a separate ML platform;
- BigQuery unless a demonstrated data volume/query requires it; and
- decorative metrics or maps with no officer decision attached.

---

## 9. Realistic demo-data story

Use **100–300 synthetic citizen signals**, not 500 unless generation and validation are automated and reliable. The dataset should contain:

- Kannada, Hindi, and English reports, plus code-switching;
- exact duplicates, paraphrases, same-need/different-incident cases, and nearby but unrelated cases;
- operational incidents that remain incidents;
- repeated incidents that roll up into one systemic development need;
- one high-volume affluent-area issue that should not automatically outrank a lower-volume high-impact underserved-area need;
- one emerging trend;
- one issue already covered by an active work, reducing or changing its recommendation;
- contradictory text/image evidence;
- low-confidence and spam cases; and
- a known ground-truth file for deduplication, classification, and ranking tests.

The dashboard should tell one coherent story: **CivicLens does not merely find the loudest complaint; it discovers the strongest review case and shows why.**

---

## 10. Tooling and MCP assessment

No additional MCP server or plugin is required to complete planning or build the MVP.

| Tool / integration | What it does | Why it helps | Required? | When |
|---|---|---|---|---|
| Browser/search research | Verifies dynamic organizer pages, public systems, datasets, and current cloud docs. | Prevents stale hackathon assumptions. | Required for planning; already available. | Stages 1–4 and final fact check before submission. |
| Playwright/browser automation | Runs real end-to-end flows and deployment smoke tests. | Protects the demo path. | Strongly recommended; already available. | From first usable citizen flow through deployment. |
| Google Cloud CLI | Deploys and inspects Cloud Run, logs, IAM, secrets, and storage. | Makes deployment reproducible. | Required only once implementation/deployment starts. | Stage 4 onward; install/configure only with approval if absent. |
| GitHub integration/CLI | Repository, actions, issues, release checks. | Useful for CI and submission hygiene. | Optional; normal Git and GitHub UI are sufficient. | Implementation and submission. |
| Figma plugin | Collaborative high-fidelity mockups. | Helpful if a designer is actively reviewing screens. | Optional, not needed for a solo prototype. | Stage 2 only if desired. |
| Database MCP | Directly inspects a hosted database. | Limited incremental value over migrations, seed scripts, and SQL tools. | Not recommended for the MVP. | Reconsider only during production operations. |

Do not install any of these silently.

---

## 11. Mistakes to avoid

- Presenting CivicLens as the first system to cluster Indian civic complaints.
- Treating report count as affected population or democratic preference.
- Calling all related reports “duplicates”; exact duplicate, same incident, related need, and same category are different relationships.
- Allowing Gemini confidence to masquerade as calibrated probability.
- Using confidence as a multiplier that suppresses urgent low-evidence reports; confidence should be displayed separately and drive review.
- Inventing real-time government data or claiming synthetic data is live.
- Showing a heatmap without the decision it supports.
- Making officers inspect hundreds of reports before understanding a need.
- Displaying precise citizen coordinates or identity in aggregate views.
- Promising WhatsApp integration without Meta setup and an approved number.
- Depending on live external data or cold services during the judged demo.
- Claiming “Digital Public Good” certification. The honest claim is “DPG-ready design” unless the project actually meets and is reviewed against the standard.

---

## 12. Stage 1 recommendations and decisions to discuss

### Recommendations

1. **Approve the needs-to-project pivot.** Keep complaint intake, but make the officer's hero object a systemic need/project candidate.
2. **Choose one pilot operating unit.** A Lok Sabha constituency best matches the brief, but ward/district data may be easier. Select only after a rapid data-availability audit.
3. **Use one operational incident and one structural need in the demo.** This proves CivicLens knows the difference.
4. **Make explainability the signature interaction.** The 87/100 breakdown is valuable only when every component traces to stored facts, source dates, and versioned rules.
5. **Treat fairness as visible product functionality.** Cap raw volume influence, show reporting coverage, and surface area-level service gaps.
6. **Remove the budget simulator.** Replace it with a decision packet and constrained intervention candidates.
7. **Avoid mandatory citizen login for reporting.** Offer optional contact/track capability; require authenticated officer roles.
8. **Demonstrate Google AI at ingestion, not as a chatbot.** A single structured multimodal call plus optional embedding step is meaningful and demo-friendly.

### Decisions for discussion before Stage 2

1. **Product scope:** approve or reject the shift from “municipal complaint prioritization” to “citizen signals → systemic need → project review candidate.”
2. **Primary official persona:** MP/constituency office, district planning officer, or municipal commissioner. The official brief points most strongly to MP/national-policy use, while the current examples point to municipal operations.
3. **Pilot geography:** real constituency/district/ward versus an explicitly synthetic demonstration geography. A real geography improves credibility but increases boundary/data-cleaning work.
4. **Citizen promise:** is CivicLens itself a redressal channel, or an intelligence layer that can later ingest from existing channels? For the MVP, the recommendation is a demonstrable direct intake plus an explicit future interoperability boundary—not a claim to replace CPGRAMS/Sahaaya.
5. **Public visibility:** recommendation is private raw evidence for officers, privacy-safe aggregate need/status pages for citizens.

Stage 2 should not begin until these product choices are resolved.

---

## Sources

[^1]: Hack2Skill, “[Build with AI: Code for Communities — Second Edition](https://hack2skill.com/event/codeforcommunities2),” accessed 11 September 2026. The dynamic official page supplied the track wording, requirements, judging weights, timeline, rules, and recommended technologies.
[^2]: Harsh Dattani, “[Build with AI: Code for Communities demo day](https://www.linkedin.com/posts/harshdattani_2026-and-beyond-are-the-years-of-tech-communities-activity-7487734426550878208-TVkh),” LinkedIn, August 2026.
[^3]: Google Developer Groups India, “[Hackathon for India’s Real World Problems with MPs](https://www.linkedin.com/posts/gdgindia_buildwithai-codeforcommunities-googlecloud-activity-7474817056278880257-yZK2),” LinkedIn, 2026.
[^4]: FoneArena, “[Google wraps up Build with AI: Code for Communities in India with 12 AI projects set for constituency pilots](https://www.fonearena.com/blog/488078/google-wraps-up-build-with-ai.html),” 23 July 2026.
[^5]: Department of Administrative Reforms & Public Grievances, “[CPGRAMS](https://pgportal.gov.in/),” Government of India, accessed September 2026.
[^6]: Department of Administrative Reforms & Public Grievances, “[About CPGRAMS and IGMS](https://pgportal.gov.in/Home/AboutUs),” Government of India, accessed September 2026.
[^7]: Ministry of Housing and Urban Affairs, “[Swachh City Platform](https://www.swachh.city/),” Government of India, accessed September 2026.
[^8]: Swachh City, “[Integration of City Apps with Swachhata App — FAQ](https://www.swachh.city/assets/files/Integration_FAQ.pdf),” accessed September 2026.
[^9]: Government of Karnataka, “[Janaspandana Integrated Public Grievance Redressal System](https://ipgrs.karnataka.gov.in/),” accessed September 2026.
[^10]: Karnataka Administrative Reforms Commission, “[Second Report](https://bbmp.gov.in/ucc_file/KarnatakaAdministrativeReforms.pdf),” 2023, section on Sahaaya 2.0.
[^11]: Janaagraha, “[Public Eye](https://www.janaagraha.org/work/public-eye/)” and “[Swachhata Technology Platform](https://www.janaagraha.org/work/swachhata-technology-platform/),” accessed September 2026.
[^12]: CivicPlus, “[SeeClickFix 311 CRM — Unified Platform](https://www.civicplus.com/seeclickfix-311-crm/unified-platform/),” accessed September 2026.
[^13]: Ushahidi, “[Platform Features](https://www.ushahidi.com/features/),” accessed September 2026.
[^14]: Decidim, “[General description and introduction](https://docs.decidim.org/en/develop/features/general-description.html),” accessed September 2026.
[^15]: Decidim, “[First steps](https://decidim.org/first-steps/),” accessed September 2026.
[^16]: Sanchi Shah et al., “[Reimagining Digital Grievance Redressal Systems for Better Participatory Governance in India](https://doi.org/10.1145/3802974.3810897),” Companion Publication of ACM DIS 2026.
[^17]: William O’Brochta, “[Politicians’ complaint response: E-governance and personal relationships](https://doi.org/10.1111/gove.12727),” *Governance*, 2023.
[^18]: Anustubh Agnihotri and Ronak Jain, “[How the content of digital complaints shapes bureaucratic responsiveness in Mumbai](https://doi.org/10.1111/gove.12889),” *Governance*, 2025.
[^19]: Digital Public Goods Alliance, “[Digital Public Goods Standard](https://www.digitalpublicgoods.net/standard),” accessed September 2026.
[^20]: Google AI for Developers, “[Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output),” updated September 2026.
[^21]: Google AI for Developers, “[Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding),” updated 2026.
[^22]: Google AI for Developers, “[Embeddings](https://ai.google.dev/gemini-api/docs/embeddings),” accessed September 2026.
[^23]: PostGIS, “[ST_DWithin](https://postgis.net/docs/ST_DWithin.html),” accessed September 2026.
[^24]: Government of India, “[Open Government Data Platform India](https://data.gov.in/),” accessed September 2026.
[^25]: Registrar General and Census Commissioner, India, “[Primary Census Abstract — Census 2011](https://www.data.gov.in/catalog/primary-census-abstract),” OGD Platform India.
[^26]: Ministry of Statistics and Programme Implementation, “[MPLADS](https://www.mplads.gov.in/mplads/Default.aspx),” Government of India.
[^27]: Ministry of Statistics and Programme Implementation, “[MPLADS Dashboard](https://mplads.gov.in/mplads/Dashboard/DashBoard.aspx),” Government of India.
[^28]: NITI Aayog, “[Reforms in Urban Planning Capacity in India](https://www.niti.gov.in/node/345),” 2021.
[^29]: Google Cloud, “[What is Cloud Run?](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run),” updated 2026.
[^30]: Google Cloud, “[Generate and manage vector embeddings in Cloud SQL for PostgreSQL](https://docs.cloud.google.com/sql/docs/postgres/generate-manage-vector-embeddings),” updated 2026.
[^31]: Google for Developers, “[Google Maps Platform pricing and billing](https://developers.google.com/maps/billing-and-pricing),” updated August 2026.
[^32]: Ministry of Electronics and Information Technology, “[Digital Personal Data Protection Rules, 2025](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025),” Government of India, notified November 2025.
