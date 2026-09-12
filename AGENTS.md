# CivicLens implementation contract

Read these in order before changing behavior:

1. `docs/STAGE_6_FINAL_DESIGN_REVIEW.md`
2. `docs/STAGE_5_BUILD_PLAN.md`
3. `docs/STAGE_3_SYSTEM_DESIGN.md`

Stage 6 is authoritative where earlier documents differ.

Non-negotiable rules:

- Build one Stage 5 milestone at a time and keep the default branch runnable.
- AI interprets evidence; deterministic rules evaluate it; humans decide.
- Safety review never competes numerically with planning priority.
- Missing or incompatible evidence is unknown, never zero.
- Report counts never represent unique citizens or affected population.
- Every public, derived, synthetic and AI-derived value keeps its provenance label.
- Use only synthetic citizen data in this prototype.
- Never log report content, audio, precise coordinates, receipt capabilities or credentials.
- Do not add Maps, image upload, embeddings, microservices, budgets, procurement or live public-data dependencies to v1.
- Run the smallest relevant checks after each change; expand testing at release gates.

