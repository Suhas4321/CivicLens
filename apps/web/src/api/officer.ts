import { z } from "zod";

import { ApiError } from "./health";

const classificationSchema = z.enum(["real_public", "derived_public", "synthetic_demo"]);

const laneItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  status: z.string(),
  category: z.string(),
  locality: z.string(),
  report_count: z.number(),
  classification: z.enum(["synthetic_demo", "ai_derived"]),
  explanation: z.string(),
});

const incidentSummarySchema = z.object({
  id: z.string(),
  key: z.string(),
  title: z.string(),
  category: z.string(),
  locality: z.string(),
  event_start: z.string(),
  report_count: z.number(),
  relationship_state: z.string(),
  classification: z.literal("synthetic_demo"),
});

const needSummarySchema = z.object({
  id: z.string(),
  key: z.string(),
  title: z.string(),
  category: z.string(),
  geography: z.string(),
  geography_kind: z.string(),
  geography_membership_method: z.string(),
  lifecycle: z.string(),
  incident_count: z.number(),
  report_count: z.number(),
  priority_band: z.string(),
  classification: z.literal("synthetic_demo"),
});

const overviewSchema = z.object({
  data_version: z.string(),
  environment_label: z.literal("Demo Officer — Synthetic Environment"),
  disclosure: z.string(),
  safety_review: z.array(laneItemSchema),
  operational_incidents: z.array(laneItemSchema),
  planning_needs: z.array(laneItemSchema),
});

const reportEvidenceSchema = z.object({
  id: z.string(),
  public_id: z.string(),
  original_text: z.string(),
  language: z.string(),
  accepted_at: z.string(),
  locality: z.string(),
  interpretation_summary: z.string(),
  classification: z.literal("synthetic_demo"),
  interpretation_classification: z.literal("ai_derived"),
});

const incidentDetailSchema = z.object({
  data_version: z.string(),
  incident: incidentSummarySchema,
  reports: z.array(reportEvidenceSchema),
  relationship_explanation: z.record(
    z.string(),
    z.union([z.string(), z.boolean(), z.number(), z.null()]),
  ),
  decision_boundary: z.string(),
});

const evidenceItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  classification: classificationSchema,
  kind: z.string(),
  value: z.union([z.string(), z.number(), z.null()]),
  unit: z.string().nullable(),
  geography: z.string(),
  geography_kind: z.string(),
  geography_vintage: z.string().nullable(),
  reference_period: z.string().nullable(),
  semantics: z.string(),
  source_url: z.string(),
  transformation: z.string().nullable(),
  contributes_to_rating: z.boolean(),
  role: z.enum(["local_decision_evidence", "broader_context"]),
  supported_inferences: z.array(z.string()),
  prohibited_inferences: z.array(z.string()),
});

const priorityComponentSchema = z.object({
  code: z.string(),
  label: z.string(),
  rating: z.number().nullable(),
  rationale: z.string(),
  evidence_refs: z.array(z.string()),
});

const candidateSchema = z.object({
  id: z.string(),
  catalogue_key: z.string(),
  catalogue_version: z.string(),
  label: z.string(),
  conditional_wording: z.string(),
  lifecycle: z.string(),
  works_overlap_outcome: z.string(),
  works_overlap_evidence: z.array(z.string()),
  prerequisites: z.array(
    z.object({
      code: z.string(),
      state: z.enum(["unknown", "required", "satisfied", "not_applicable"]),
    }),
  ),
  uncertainty: z.array(z.string()),
  decision_boundary: z.string(),
});

const needWorkspaceSchema = z.object({
  data_version: z.string(),
  need: needSummarySchema,
  hypothesis: z.string(),
  hypothesis_label: z.literal("Suspected Civic Need"),
  alternative_hypotheses: z.array(z.string()),
  incidents: z.array(incidentSummarySchema),
  evidence: z.array(evidenceItemSchema),
  priority: z.object({
    eligible: z.boolean(),
    band: z.enum(["high", "moderate", "lower", "not_comparable"]),
    components: z.array(priorityComponentSchema),
    sensitivity_status: z.enum(["stable", "sensitive", "not_comparable"]),
    sensitivity_profiles: z.array(z.string()),
    abstention_codes: z.array(z.string()),
    policy_notice: z.string(),
  }),
  candidate: candidateSchema,
  evidence_notice: z.string(),
  human_decision_notice: z.string(),
});

export type OfficerOverview = z.infer<typeof overviewSchema>;
export type NeedWorkspace = z.infer<typeof needWorkspaceSchema>;
export type IncidentDetail = z.infer<typeof incidentDetailSchema>;

async function getJson<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" }, signal });
  if (!response.ok) {
    throw new ApiError(
      `Request failed (${response.status})`,
      response.status,
      response.headers.get("X-Correlation-ID"),
    );
  }
  return schema.parse(await response.json());
}

export function fetchOfficerOverview(signal?: AbortSignal): Promise<OfficerOverview> {
  return getJson("/api/v1/officer/overview", overviewSchema, signal);
}

export function fetchNeedWorkspace(id: string, signal?: AbortSignal): Promise<NeedWorkspace> {
  return getJson(`/api/v1/officer/needs/${encodeURIComponent(id)}`, needWorkspaceSchema, signal);
}

export function fetchIncidentDetail(id: string, signal?: AbortSignal): Promise<IncidentDetail> {
  return getJson(`/api/v1/officer/incidents/${encodeURIComponent(id)}`, incidentDetailSchema, signal);
}
