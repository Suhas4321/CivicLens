import { z } from "zod";

import { ApiError } from "./health";
import { getSession, sessionHeaders } from "./decisions";

const reviewActionSchema = z.enum([
  "confirm_bounded_incident",
  "keep_separate",
  "verify_safety",
  "refer_safety",
  "dismiss_safety",
]);

const workflowReviewSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  report_id: z.string(),
  action: reviewActionSchema,
  reason: z.string(),
  evidence_digest: z.string(),
  expected_version: z.number(),
  entity_version_after: z.number(),
  supersedes_id: z.string().nullable(),
  created_at: z.string(),
  record_notice: z.string(),
});

export type WorkflowReview = z.infer<typeof workflowReviewSchema>;
export type ReviewAction = z.infer<typeof reviewActionSchema>;

async function responseError(response: Response): Promise<never> {
  throw new ApiError(
    `Request failed (${response.status})`,
    response.status,
    response.headers.get("X-Correlation-ID"),
  );
}

export async function fetchWorkflowReviews(reportId: string): Promise<WorkflowReview[]> {
  const session = await getSession();
  const response = await fetch(
    `/api/v1/officer/reports/${encodeURIComponent(reportId)}/reviews`,
    { headers: sessionHeaders(session) },
  );
  if (!response.ok) return responseError(response);
  return z.array(workflowReviewSchema).parse(await response.json());
}

export async function recordWorkflowReview(
  reportId: string,
  payload: { action: ReviewAction; reason: string; expected_version: number },
): Promise<WorkflowReview> {
  const session = await getSession();
  const response = await fetch(
    `/api/v1/officer/reports/${encodeURIComponent(reportId)}/reviews`,
    {
      method: "POST",
      headers: {
        ...sessionHeaders(session),
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) return responseError(response);
  return workflowReviewSchema.parse(await response.json());
}
