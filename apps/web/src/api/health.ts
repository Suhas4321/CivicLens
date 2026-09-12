import { z } from "zod";

const versionResponseSchema = z.object({
  application: z.literal("civiclens-api"),
  version: z.string(),
  environment: z.string(),
  schema_version: z.string(),
  prompt_version: z.string(),
  rules_version: z.string(),
  catalogue_version: z.string(),
  seed_version: z.string(),
  public_snapshot_version: z.string(),
});

export type VersionResponse = z.infer<typeof versionResponseSchema>;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly correlationId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchVersion(signal?: AbortSignal): Promise<VersionResponse> {
  const response = await fetch("/api/v1/health/version", {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new ApiError(
      `Health request failed (${response.status})`,
      response.status,
      response.headers.get("X-Correlation-ID"),
    );
  }

  return versionResponseSchema.parse(await response.json());
}
