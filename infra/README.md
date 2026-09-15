# CivicLens infrastructure

The prototype targets one Firebase/Google Cloud project:

- Firebase Hosting for the static web client, the `/api/**` rewrite, and the basemap tile archive
- one Cloud Run service for public API and authenticated task handlers
- Cloud SQL PostgreSQL 17 **with the PostGIS extension enabled**
- one private regional Cloud Storage bucket for report photos, resolution-evidence photos and short voice attachments
- one regional Cloud Tasks queue
- Vertex AI Gemini
- Firebase anonymous authentication, with App Check attestation

Provisioning remains explicit and approval-gated. Do not create service-account JSON keys; use authenticated developer tooling and least-privilege service identities.

## No mapping vendor

There is **no Google Maps API, no mapping API key, and no third-party tile account** in this project. The basemap is a Protomaps `.pmtiles` archive extracted from OpenStreetMap for the Bengaluru South bounding box and committed as a static asset under `apps/web/public/tiles/`. Firebase Hosting serves it over HTTP range requests, which is what `.pmtiles` requires; MapLibre GL reads it client-side.

Consequences worth being explicit about: nothing here can incur mapping charges, no key can leak or expire, no quota can trip during a demo, and the map keeps working offline. The public OpenStreetMap tile servers are **not** used — their usage policy does not permit application traffic. `© OpenStreetMap contributors` must be visible on every rendered map; the data is ODbL-licensed.

## Release sequence

1. Create one Artifact Registry repository, private Cloud SQL 17 instance, private media bucket and Cloud Tasks queue in `asia-south1`. **Enable the `postgis` extension on the instance before migrating.**
2. Store database credentials, the reporter-key HMAC pepper and any developer-only API key in Secret Manager. Production Gemini uses the Cloud Run service identity with Vertex AI, not an API key.
3. Run the Alembic migration as a one-off release job, then load the OpenStreetMap spatial layers (roads, way-nodes, localities, POIs) and seed the demo corpus idempotently.
4. Build `apps/api/Dockerfile` with `infra/cloudbuild-api.yaml`, deploy a tagged Cloud Run revision with a bounded instance count, and set all three persistence backends to `postgres`.
5. Smoke-test readiness, one end-to-end report submission with a photo, and the officer worklist before shifting traffic. Deploy Firebase Hosting only after the API revision is healthy. **Confirm the basemap loads and renders attribution.**

The repository intentionally contains no live project IDs, passwords, secret values or automatic provisioning command that could mutate a cloud account without review.
