import { z } from "zod";

import { ApiError } from "./health";

const sessionSchema = z.object({
  session_id: z.string(),
  access_token: z.string(),
  actor_role: z.literal("demo_officer"),
  expires_at: z.string(),
  disclosure: z.string(),
});

const decisionSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  need_id: z.string(),
  candidate_id: z.string().nullable(),
  disposition: z.enum(["refer", "defer", "reject"]),
  actor_role: z.literal("demo_officer"),
  reason_code: z.string(),
  reason_text: z.string().nullable(),
  next_step: z.string().nullable(),
  next_review_date: z.string().nullable(),
  evidence_digest: z.string(),
  expected_entity_version: z.number(),
  entity_version_after: z.number(),
  supersedes_id: z.string().nullable(),
  created_at: z.string(),
  record_notice: z.string(),
});

const SESSION_KEY = "civiclens.demo-officer-session.v1";

export type HumanDecision = z.infer<typeof decisionSchema>;
type DemoSession = z.infer<typeof sessionSchema>;

export type DecisionPayload = {
  disposition: "refer" | "defer" | "reject";
  reason_code:
    | "FIELD_VERIFICATION"
    | "FEASIBILITY_REVIEW"
    | "EVIDENCE_GAP"
    | "WORKS_OVERLAP_REVIEW"
    | "NOT_SUPPORTED";
  reason_text: string | null;
  next_step: string | null;
  next_review_date: string | null;
  expected_entity_version: number;
};

async function responseError(response: Response): Promise<never> {
  throw new ApiError(
    `Request failed (${response.status})`,
    response.status,
    response.headers.get("X-Correlation-ID"),
  );
}

async function getSession(): Promise<DemoSession> {
  const stored = sessionStorage.getItem(SESSION_KEY);
  if (stored) {
    try {
      const parsed = sessionSchema.safeParse(JSON.parse(stored));
      if (parsed.success && new Date(parsed.data.expires_at).getTime() > Date.now()) {
        return parsed.data;
      }
    } catch {
      // Corrupt browser state is discarded and never sent to the API.
    }
    sessionStorage.removeItem(SESSION_KEY);
  }

  const response = await fetch("/api/v1/demo-sessions", { method: "POST" });
  if (!response.ok) return responseError(response);
  const created = sessionSchema.parse(await response.json());
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(created));
  return created;
}

function sessionHeaders(session: DemoSession): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${session.access_token}`,
    "X-Demo-Session-ID": session.session_id,
  };
}

export async function fetchDecisionHistory(needId: string): Promise<HumanDecision[]> {
  const session = await getSession();
  const response = await fetch(`/api/v1/officer/needs/${encodeURIComponent(needId)}/decisions`, {
    headers: sessionHeaders(session),
  });
  if (!response.ok) return responseError(response);
  return z.array(decisionSchema).parse(await response.json());
}

export async function recordDecision(
  needId: string,
  payload: DecisionPayload,
): Promise<HumanDecision> {
  const session = await getSession();
  const response = await fetch(`/api/v1/officer/needs/${encodeURIComponent(needId)}/decisions`, {
    method: "POST",
    headers: {
      ...sessionHeaders(session),
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) return responseError(response);
  return decisionSchema.parse(await response.json());
}
