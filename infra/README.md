# CivicLens infrastructure

The prototype targets one Firebase/Google Cloud project:

- Firebase Hosting for the static web client and `/api/**` rewrite
- one Cloud Run service for public API and authenticated task handlers
- Cloud SQL PostgreSQL 17
- one private regional Cloud Storage bucket for short voice attachments
- one regional Cloud Tasks queue
- Vertex AI Gemini
- Firebase anonymous authentication

Provisioning remains explicit and approval-gated. Do not create service-account JSON keys; use authenticated developer tooling and least-privilege service identities.

## Release sequence

1. Create one Artifact Registry repository, private Cloud SQL 17 instance, private media bucket and Cloud Tasks queue in `asia-south1`.
2. Store database credentials and any developer-only API key in Secret Manager. Production Gemini uses the Cloud Run service identity with Vertex AI, not an API key.
3. Run the Alembic migration as a one-off release job, then seed the frozen demo snapshot idempotently.
4. Build `apps/api/Dockerfile` with `infra/cloudbuild-api.yaml`, deploy a tagged Cloud Run revision with a bounded instance count, and set all three persistence backends to `postgres`.
5. Smoke-test readiness and the Golden Demo before shifting traffic. Deploy Firebase Hosting only after the API revision is healthy.

The repository intentionally contains no live project IDs, passwords, secret values or automatic provisioning command that could mutate a cloud account without review.
