import { z } from "zod";

import { ApiError } from "./health";

/**
 * Report submission.
 *
 * One thing here needs explaining, because it looks like defensiveness and is
 * actually a correctness requirement.
 *
 * `POST /api/v1/reports` declares its form fields explicitly, and FastAPI
 * silently ignores any field it did not declare. So if this client sends a
 * `photo` before the endpoint accepts one, the request succeeds, the citizen is
 * shown a receipt, and their photo is discarded without anybody being told. That
 * is the worst possible failure for a service whose whole claim is that evidence
 * is handled honestly.
 *
 * The fix is for the server to acknowledge what it stored: `photo_received` and
 * `service_code_recorded` on the accept response. `acceptedSchema` marks them
 * optional so this client works against both the current endpoint and the
 * extended one, and `submitReport` reports `photoStored` as *confirmed by the
 * server* rather than *sent by us*. A missing acknowledgement therefore reads as
 * "not stored", which is the safe direction to be wrong in.
 */

const acceptedSchema = z.object({
  public_id: z.string(),
  status: z.literal("received"),
  accepted_at: z.string(),
  message: z.string(),
  /** Present once the endpoint accepts photos. Absent means the photo was dropped. */
  photo_received: z.boolean().optional(),
  service_code_recorded: z.boolean().optional(),
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
  /** One of the 12 codes in config/categories. Chosen by the reporter, not inferred. */
  service_code?: string;
  latitude?: number;
  longitude?: number;
  photo?: File;
};

export type ReportAccepted = z.infer<typeof acceptedSchema>;
export type Receipt = z.infer<typeof receiptSchema>;

export type SubmissionReceipt = {
  accepted: ReportAccepted;
  capability: string;
  /** True only when a photo was sent AND the server confirmed it stored it. */
  photoStored: boolean;
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
  body.set("consent", String(payload.consent));
  body.set("synthetic_demo_confirmation", String(payload.synthetic_demo_confirmation));

  if (payload.service_code) {
    body.set("service_code", payload.service_code);
  }
  // Coordinates travel as a pair or not at all; ReportCreateRequest rejects a
  // lone latitude, so sending one would turn a UI slip into a 422.
  if (payload.latitude !== undefined && payload.longitude !== undefined) {
    body.set("latitude", String(payload.latitude));
    body.set("longitude", String(payload.longitude));
  }
  // Sent unmodified: the server reads EXIF capture time and location from these
  // exact bytes, and re-encoding in the browser would destroy both.
  if (payload.photo) {
    body.set("photo", payload.photo, payload.photo.name);
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
  const accepted = acceptedSchema.parse(await response.json());
  return {
    accepted,
    capability,
    photoStored: payload.photo !== undefined && accepted.photo_received === true,
  };
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
