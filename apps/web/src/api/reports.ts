import { z } from "zod";

import { ApiError } from "./health";

const acceptedSchema = z.object({
  public_id: z.string(),
  status: z.literal("received"),
  accepted_at: z.string(),
  message: z.string(),
});

const receiptSchema = z.object({
  public_id: z.string(),
  status: z.enum(["received", "analysing", "processed", "needs_review"]),
  accepted_at: z.string(),
  generalized_area: z.string(),
  evidence_class: z.literal("synthetic_demo"),
  analysis_class: z.enum(["pending", "stored_sample", "fresh_fixture", "fresh_ai"]),
  analysis_state: z.string(),
  message: z.string(),
});

export type ReportPayload = {
  description: string;
  language_hint: "en" | "kn" | "hi" | "mixed";
  locality_label: string;
  consent: true;
  synthetic_demo_confirmation: true;
  voice?: Blob;
};

export type ReportAccepted = z.infer<typeof acceptedSchema>;
export type Receipt = z.infer<typeof receiptSchema>;

export type SubmissionReceipt = {
  accepted: ReportAccepted;
  capability: string;
};

function newCapability(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function apiError(response: Response): Promise<never> {
  throw new ApiError(
    `Request failed (${response.status})`,
    response.status,
    response.headers.get("X-Correlation-ID"),
  );
}

export async function submitReport(payload: ReportPayload): Promise<SubmissionReceipt> {
  const capability = newCapability();
  const body = new FormData();
  body.set("description", payload.description);
  body.set("language_hint", payload.language_hint);
  body.set("locality_label", payload.locality_label);
  body.set("consent", "true");
  body.set("synthetic_demo_confirmation", "true");
  if (payload.voice) {
    body.set("voice", payload.voice, "synthetic-voice.webm");
  }
  const response = await fetch("/api/v1/reports", {
    method: "POST",
    headers: {
      "Idempotency-Key": crypto.randomUUID(),
      "X-Receipt-Capability": capability,
    },
    body,
  });
  if (!response.ok) {
    return apiError(response);
  }
  return { accepted: acceptedSchema.parse(await response.json()), capability };
}

export async function fetchReceipt(
  publicId: string,
  capability: string,
  signal?: AbortSignal,
): Promise<Receipt> {
  const response = await fetch(`/api/v1/receipts/${encodeURIComponent(publicId)}`, {
    headers: {
      Accept: "application/json",
      "X-Receipt-Capability": capability,
    },
    signal,
  });
  if (!response.ok) {
    return apiError(response);
  }
  return receiptSchema.parse(await response.json());
}
