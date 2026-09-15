import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Clock,
  Info,
  Languages,
  Send,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AGENCY_META, type Category } from "@/api/priority";
import { loadCategories } from "@/api/pendingBackend";
import { submitReport, type ReportPayload } from "@/api/reports";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { CategoryGrid, CategorySummary } from "./CategoryGrid";
import { PhotoCapture, type PhotoSelection } from "./PhotoCapture";
import { LocationPicker, type ReportLocation } from "./LocationPicker";

/**
 * Citizen report intake, rebuilt as three steps.
 *
 * The previous version asked for free text, a locality string and an optional
 * 30-second voice clip. That produced a report a computer could not act on: no
 * category means no responsible agency and no statutory deadline, no coordinates
 * means no grouping with the neighbour who reported the same pothole, and the
 * voice blob was uploaded and then never transcribed, never read by the
 * interpreter and never shown to an officer. Those are gone. What replaced them
 * is the smallest set of facts that makes a report *routable*:
 *
 *   1. **What** — one of 12 categories, which fixes the agency and the deadline.
 *   2. **Where** — a device position and a landmark, which is what grouping runs on.
 *   3. **Confirm** — the reporter sees exactly what they are sending.
 *
 * Steps exist rather than one long form because this is a phone-first, one-hand,
 * possibly-standing-in-the-rain interaction, and because each step can be checked
 * before the next is offered. Nothing is validated at the end that could have
 * been validated at the start.
 *
 * The description asks for a few words, not a paragraph. It used to demand
 * twenty characters, which is a real barrier for someone who would rather not
 * type — and unnecessary, because the category now fixes the agency and the
 * deadline, the photo carries the severity and the location carries the
 * grouping. Four characters is the floor, and that number is not arbitrary: it is
 * the minimum the interpreter accepts, so anything shorter would be accepted at
 * intake and then rejected during analysis. See the comment on
 * `ReportCreateRequest.description`.
 */

type Language = ReportPayload["language_hint"];
type Step = 1 | 2 | 3;

/**
 * Mirrors `ReportCreateRequest.description` and
 * `InterpretationRequest.text` on the API, which both use 4. If it is raised
 * there it must be raised here, or the reporter fills in three steps and is
 * refused at the end.
 */
const MIN_DESCRIPTION = 4;

const STEPS: { id: Step; label: string; labelKn: string }[] = [
  { id: 1, label: "What", labelKn: "ಏನು" },
  { id: 2, label: "Where", labelKn: "ಎಲ್ಲಿ" },
  { id: 3, label: "Confirm", labelKn: "ಖಚಿತ" },
];

export function ReportPage() {
  const navigate = useNavigate();

  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: ({ signal }) => loadCategories(signal),
    staleTime: 60 * 60 * 1000,
  });

  const [step, setStep] = useState<Step>(1);
  const [serviceCode, setServiceCode] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [language, setLanguage] = useState<Language>("kn");
  const [location, setLocation] = useState<ReportLocation | null>(null);
  const [landmark, setLandmark] = useState("");
  const [photo, setPhoto] = useState<PhotoSelection | null>(null);
  const [consent, setConsent] = useState(false);
  const [synthetic, setSynthetic] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const categories = categoriesQuery.data?.data.categories;
  const category = useMemo(
    () => categories?.find((item) => item.code === serviceCode) ?? null,
    [categories, serviceCode],
  );

  // The landmark is what the server stores as `locality_label`, and it is a
  // required field there with a 3-character minimum. Falling back to the
  // category label keeps a location-only report submittable rather than
  // failing validation on a field the reporter was told was optional.
  const localityLabel = landmark.trim().length >= 3 ? landmark.trim() : (category?.label_en ?? "");

  const canLeaveStep1 = serviceCode !== null && description.trim().length >= MIN_DESCRIPTION;
  const canLeaveStep2 = location !== null || landmark.trim().length >= 3;
  const canSubmit = canLeaveStep1 && canLeaveStep2 && consent && synthetic && !submitting;

  async function onSubmit() {
    if (!canSubmit || !serviceCode) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await submitReport({
        description: description.trim(),
        language_hint: language,
        locality_label: localityLabel,
        consent: true,
        synthetic_demo_confirmation: true,
        service_code: serviceCode,
        ...(location
          ? { latitude: location.latitude, longitude: location.longitude }
          : {}),
        ...(photo ? { photo: photo.file } : {}),
      });
      navigate(`/receipt/${result.accepted.public_id}`, {
        state: {
          capability: result.capability,
          // Carried through so the receipt can say whether the photo was stored
          // instead of assuming it was.
          photoAttached: photo !== null,
          photoStored: result.photoStored,
        },
      });
    } catch {
      setError("We could not send the report. Check your connection and try again.");
      setSubmitting(false);
    }
  }

  return (
    <section className="page-shell py-8 sm:py-12">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-2 text-base font-medium text-slate-600 no-underline hover:text-slate-950"
      >
        <ArrowLeft className="size-4" aria-hidden /> ಹಿಂದೆ · Back
      </Link>

      <div className="max-w-2xl">
        <h1 className="text-balance text-3xl font-semibold tracking-[-0.03em] text-slate-950 sm:text-4xl">
          ಸಮಸ್ಯೆಯನ್ನು ತಿಳಿಸಿ
        </h1>
        <p className="mt-1 text-xl font-medium text-slate-700">Report a problem</p>
        <p className="mt-3 text-base leading-7 text-slate-600">
          Three short steps. You will get a reference number you can check later.
        </p>
      </div>

      <StepRail current={step} />

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="min-w-0">
          {step === 1 ? (
            <StepCard
              title="ಯಾವ ರೀತಿಯ ಸಮಸ್ಯೆ?"
              subtitle="What kind of problem is it?"
              hint="Pick the closest one. Each shows which office is responsible and how many days they have."
            >
              {categoriesQuery.isPending ? (
                <p className="text-base text-slate-500">Loading the list…</p>
              ) : categoriesQuery.isError || !categories ? (
                <Alert variant="destructive">
                  <TriangleAlert aria-hidden />
                  <AlertDescription>
                    The category list could not be loaded, so a report cannot be routed right
                    now. Please try again shortly.
                  </AlertDescription>
                </Alert>
              ) : (
                <CategoryGrid
                  categories={categories}
                  value={serviceCode}
                  onChange={(code) => {
                    setServiceCode(code);
                    setStep(2);
                  }}
                />
              )}
            </StepCard>
          ) : null}

          {step === 2 ? (
            <StepCard
              title="ಎಲ್ಲಿದೆ? ಫೋಟೋ ಇದೆಯೇ?"
              subtitle="Where is it, and do you have a photo?"
              hint="A location lets us join your report with others about the same problem."
            >
              <div className="space-y-7">
                <LocationPicker
                  location={location}
                  onLocation={setLocation}
                  landmark={landmark}
                  onLandmark={setLandmark}
                />

                <div className="border-t border-slate-200 pt-6">
                  <PhotoCapture
                    value={photo}
                    onChange={setPhoto}
                    pin={
                      location
                        ? { latitude: location.latitude, longitude: location.longitude }
                        : null
                    }
                  />
                </div>

                <div className="space-y-2 border-t border-slate-200 pt-6">
                  <Label
                    htmlFor="description"
                    className="text-[1.0625rem] font-semibold text-slate-950"
                  >
                    ವಿವರ · What is wrong? <span className="font-normal text-slate-500">
                      (a few words is enough)
                    </span>
                  </Label>
                  <Textarea
                    id="description"
                    maxLength={2000}
                    required
                    minLength={MIN_DESCRIPTION}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="ಗುಂಡಿ ಇದೆ · big pothole, water not coming, wire hanging…"
                    className="min-h-28 resize-y rounded-xl border-2 border-slate-300 bg-white px-4 py-3 text-base leading-7"
                  />
                  <div className="flex items-center justify-between gap-4 text-sm text-slate-500">
                    <span>Please do not include your name, phone number or address.</span>
                    <span className="numeric shrink-0">{description.length}/2000</span>
                  </div>
                  {/* Written in the reporter's terms — why the words are wanted,
                    * not that a validator is unsatisfied. */}
                  {description.trim().length < MIN_DESCRIPTION ? (
                    <p className="text-sm text-slate-600">
                      Kannada, English, Hindi or a mix — whatever is easiest. A few words let your
                      report be matched with your neighbours' reports about the same thing.
                    </p>
                  ) : null}
                </div>

                <div className="max-w-xs space-y-2">
                  <Label className="flex items-center gap-2 text-[1.0625rem] font-semibold text-slate-950">
                    <Languages className="size-4 text-lane-discretionary" aria-hidden /> ಭಾಷೆ ·
                    Language
                  </Label>
                  <Select value={language} onValueChange={(value) => setLanguage(value as Language)}>
                    <SelectTrigger className="h-12 w-full rounded-xl border-2 border-slate-300 bg-white px-4 text-base">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="kn">ಕನ್ನಡ · Kannada</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="hi">हिंदी · Hindi</SelectItem>
                      <SelectItem value="mixed">Mixed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </StepCard>
          ) : null}

          {step === 3 && category ? (
            <StepCard
              title="ಪರಿಶೀಲಿಸಿ"
              subtitle="Check and send"
              hint="This is exactly what will be sent. Nothing else about you is included."
            >
              <dl className="divide-y divide-slate-200 border-y border-slate-200">
                <Row label="Problem">
                  <CategorySummary category={category} />
                </Row>
                <Row label="Goes to">
                  {category.agency ? (
                    <span>
                      <strong className="font-semibold">{AGENCY_META[category.agency].name}</strong>
                      <span className="mt-0.5 block text-sm text-slate-600">
                        {AGENCY_META[category.agency].nameKn}
                      </span>
                    </span>
                  ) : (
                    <span className="text-slate-600">
                      An officer will route this to the right office.
                    </span>
                  )}
                </Row>
                <Row label="Deadline">
                  <span className="inline-flex items-center gap-2">
                    <Clock className="size-4 text-slate-500" aria-hidden />
                    <span className="numeric font-semibold">
                      {category.sla_days === 1 ? "1 day" : `${category.sla_days} days`}
                    </span>
                    <span className="text-sm text-slate-600">from the first report</span>
                  </span>
                </Row>
                <Row label="Where">
                  {location ? (
                    <span>
                      <span className="numeric block">
                        {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)}
                      </span>
                      {landmark.trim() ? (
                        <span className="mt-0.5 block text-sm text-slate-600">
                          {landmark.trim()}
                        </span>
                      ) : null}
                    </span>
                  ) : (
                    <span>{landmark.trim() || "Not given"}</span>
                  )}
                </Row>
                <Row label="Photo">
                  {photo ? (
                    <span className="numeric">{photo.file.name}</span>
                  ) : (
                    <span className="text-slate-600">
                      None. An officer may need to visit before acting.
                    </span>
                  )}
                </Row>
                <Row label="What is wrong">
                  <span className="whitespace-pre-wrap">{description.trim()}</span>
                </Row>
              </dl>

              <div className="mt-6 space-y-3 rounded-xl border-2 border-slate-200 bg-slate-50 p-4">
                <label className="flex cursor-pointer items-start gap-3 text-base leading-6 text-slate-800">
                  <Checkbox
                    checked={synthetic}
                    onCheckedChange={(checked) => setSynthetic(checked === true)}
                    className="mt-1 size-5"
                  />
                  <span>
                    <strong className="font-semibold text-slate-950">
                      This is an invented demo report.
                    </strong>
                    <span className="mt-0.5 block text-sm text-slate-600">
                      CivicLens is a prototype and accepts synthetic reports only.
                    </span>
                  </span>
                </label>
                <label className="flex cursor-pointer items-start gap-3 text-base leading-6 text-slate-800">
                  <Checkbox
                    checked={consent}
                    onCheckedChange={(checked) => setConsent(checked === true)}
                    className="mt-1 size-5"
                  />
                  <span>I agree to this report being processed for the demonstration.</span>
                </label>
              </div>

              {error ? (
                <Alert variant="destructive" className="mt-4">
                  <Info aria-hidden />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
            </StepCard>
          ) : null}

          <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            {step > 1 ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep((step - 1) as Step)}
                className="gap-2 px-5 text-base"
              >
                <ArrowLeft className="size-4" aria-hidden /> Back
              </Button>
            ) : (
              <span />
            )}

            {step === 3 ? (
              <Button
                type="button"
                onClick={() => void onSubmit()}
                disabled={!canSubmit}
                className="gap-2 px-6 text-base"
              >
                {submitting ? "Sending…" : "Send report"}
                {submitting ? null : <Send className="size-4" aria-hidden />}
              </Button>
            ) : (
              <Button
                type="button"
                onClick={() => setStep((step + 1) as Step)}
                disabled={step === 1 ? !canLeaveStep1 : !canLeaveStep2}
                className="gap-2 px-6 text-base"
              >
                Continue <ArrowRight className="size-4" aria-hidden />
              </Button>
            )}
          </div>

          {/* Why "Continue" is unavailable, said next to the button. A disabled
            * control with no explanation is the thing that makes software feel
            * broken rather than strict. */}
          {step === 1 && !canLeaveStep1 ? (
            <p className="mt-3 text-sm text-slate-600">
              {serviceCode === null
                ? "Please choose what kind of problem this is."
                : "Please add a few words about what is wrong."}
            </p>
          ) : null}
          {step === 2 && !canLeaveStep2 ? (
            <p className="mt-3 text-sm text-slate-600">
              Please either share your location or type a nearby landmark.
            </p>
          ) : null}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24">
          {category ? (
            <div className="rounded-2xl border-2 border-slate-200 bg-white p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                Your report so far
              </p>
              <div className="mt-3">
                <CategorySummary category={category} />
              </div>
              <ul className="mt-4 space-y-2 text-sm">
                <Done done={location !== null || landmark.trim().length >= 3}>Location</Done>
                <Done done={photo !== null}>Photo</Done>
                <Done done={description.trim().length >= MIN_DESCRIPTION}>What is wrong</Done>
              </ul>
            </div>
          ) : null}

          <div className="rounded-2xl bg-officer-chrome p-5 text-white">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-white/60">
              What happens next
            </p>
            <ol className="mt-4 space-y-4 text-sm leading-6">
              {[
                "You get a reference number straight away.",
                "Reports about the same problem are grouped together.",
                "Life-safety problems skip the queue entirely.",
                "Everything else is ranked, and the reasons are shown.",
              ].map((item, index) => (
                <li key={item} className="flex gap-3">
                  <span className="numeric grid size-6 shrink-0 place-items-center rounded-full bg-white/15 text-xs font-semibold">
                    {index + 1}
                  </span>
                  <span className="pt-0.5 text-white/90">{item}</span>
                </li>
              ))}
            </ol>
          </div>

          <p className="flex gap-3 rounded-2xl border-2 border-lane-safety-border bg-lane-safety-surface p-4 text-sm leading-6 text-lane-safety-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              <strong className="font-semibold">This is not an emergency service.</strong> For a
              fire, a medical emergency or a live electrical danger, call the emergency number
              first.
            </span>
          </p>

          <p className="flex gap-3 px-1 text-sm leading-6 text-slate-600">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-slate-500" aria-hidden />
            <span>
              A report is treated as evidence, not as an established fact. We store the place, not
              who you are.
            </span>
          </p>
        </aside>
      </div>
    </section>
  );
}

function StepRail({ current }: { current: Step }) {
  return (
    <ol className="mt-7 flex items-center gap-2" aria-label="Progress">
      {STEPS.map((item, index) => {
        const state = item.id < current ? "done" : item.id === current ? "current" : "todo";
        return (
          <li key={item.id} className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "grid size-9 shrink-0 place-items-center rounded-full text-sm font-semibold",
                state === "done" && "bg-lane-discretionary text-white",
                state === "current" &&
                  "bg-white text-lane-discretionary ring-2 ring-lane-discretionary",
                state === "todo" && "bg-slate-200 text-slate-500",
              )}
              aria-current={state === "current" ? "step" : undefined}
            >
              {state === "done" ? <Check className="size-4" aria-hidden /> : index + 1}
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  "block truncate text-sm font-semibold",
                  state === "todo" ? "text-slate-500" : "text-slate-950",
                )}
              >
                {item.labelKn}
              </span>
              <span className="block truncate text-xs text-slate-500">{item.label}</span>
            </span>
            {index < STEPS.length - 1 ? (
              <span
                className={cn(
                  "hidden h-0.5 flex-1 rounded-full sm:block",
                  state === "done" ? "bg-lane-discretionary" : "bg-slate-200",
                )}
                aria-hidden
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function StepCard({
  title,
  subtitle,
  hint,
  children,
}: {
  title: string;
  subtitle: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-3xl border-2 border-slate-200 bg-white p-5 sm:p-7">
      <h2 className="text-2xl font-semibold tracking-[-0.02em] text-slate-950">{title}</h2>
      <p className="mt-0.5 text-lg font-medium text-slate-700">{subtitle}</p>
      <p className="mt-2 max-w-xl text-base leading-7 text-slate-600">{hint}</p>
      <div className="mt-6">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-4 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</dt>
      <dd className="min-w-0 text-base text-slate-950">{children}</dd>
    </div>
  );
}

function Done({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span
        className={cn(
          "grid size-5 shrink-0 place-items-center rounded-full",
          done ? "bg-lane-discretionary text-white" : "bg-slate-200 text-slate-400",
        )}
      >
        {done ? <Check className="size-3" aria-hidden /> : null}
      </span>
      <span className={done ? "text-slate-800" : "text-slate-500"}>{children}</span>
    </li>
  );
}
