import { Check, Info, LocateFixed, MapPin, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Where the problem is.
 *
 * There is no interactive basemap here yet. The self-hosted Protomaps `.pmtiles`
 * extract is a deployment artifact that has not been built, and this project uses
 * no Google Maps key and no public OpenStreetMap tile server. Rather than ship a
 * fake map or a dead grey box, this collects the two things that actually drive
 * grouping — a device position and a human landmark — and says plainly what it
 * has. A draggable pin lands when the basemap does, behind the same interface.
 *
 * The landmark matters more than it looks. The 2026-09-15 OSM ingest resolves
 * localities only to adjacent-suburb accuracy, and 97% of `place=*` objects in
 * Bengaluru South are bare nodes with no boundary. A reporter typing "opposite
 * the BDA complex" is often better ground truth than anything derivable from
 * geometry alone.
 */

export type ReportLocation = {
  latitude: number;
  longitude: number;
  /** GPS accuracy radius in metres, as reported by the device. */
  accuracyM: number;
  source: "device";
};

const ACCURACY_POOR_M = 100;

/** Bengaluru South, generously bounded. Matches the ingest bbox in config/geography. */
const BBOX = { minLon: 77.45, minLat: 12.8, maxLon: 77.75, maxLat: 13.05 };

function insideServiceArea(latitude: number, longitude: number): boolean {
  return (
    longitude >= BBOX.minLon &&
    longitude <= BBOX.maxLon &&
    latitude >= BBOX.minLat &&
    latitude <= BBOX.maxLat
  );
}

export function LocationPicker({
  location,
  onLocation,
  landmark,
  onLandmark,
}: {
  location: ReportLocation | null;
  onLocation: (location: ReportLocation | null) => void;
  landmark: string;
  onLandmark: (value: string) => void;
}) {
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function locate() {
    setError(null);
    if (!navigator.geolocation) {
      setError("This browser cannot share a location. Please describe the landmark instead.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        const { latitude, longitude, accuracy } = position.coords;
        onLocation({
          latitude,
          longitude,
          accuracyM: Math.round(accuracy),
          source: "device",
        });
      },
      (positionError) => {
        setLocating(false);
        // Distinguishing these matters: a denied permission is the reporter's
        // choice and needs no apology, while a timeout is worth retrying.
        setError(
          positionError.code === positionError.PERMISSION_DENIED
            ? "Location permission was declined. Describing the landmark below works too."
            : "We could not get a location just now. Please describe the landmark below.",
        );
      },
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 60_000 },
    );
  }

  const outsideArea = location !== null && !insideServiceArea(location.latitude, location.longitude);
  const poorAccuracy = location !== null && location.accuracyM > ACCURACY_POOR_M;

  return (
    <div className="space-y-4">
      {location === null ? (
        <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-5 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-lane-discretionary-surface text-lane-discretionary-ink">
            <MapPin className="size-7" aria-hidden />
          </span>
          <p className="mt-3 text-[1.0625rem] font-semibold text-slate-950">
            ಸ್ಥಳ ಗುರುತಿಸಿ · Mark the place
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-600">
            Stand near the problem if you can. This is how we tell your report apart from a
            similar one on the next street.
          </p>
          <Button
            type="button"
            onClick={locate}
            disabled={locating}
            className="mt-4 gap-2 px-5 text-base"
          >
            <LocateFixed className="size-5" aria-hidden />
            {locating ? "Finding you…" : "Use my location"}
          </Button>
        </div>
      ) : (
        <div className="rounded-2xl border-2 border-lane-discretionary-border bg-lane-discretionary-surface p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-lane-discretionary text-white">
                <Check className="size-5" aria-hidden />
              </span>
              <div>
                <p className="font-semibold text-slate-950">Location captured</p>
                <p className="numeric mt-0.5 text-sm text-slate-700">
                  {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)} · accurate to
                  about {location.accuracyM} m
                </p>
              </div>
            </div>
            <Button type="button" variant="outline" onClick={locate} disabled={locating}>
              Redo
            </Button>
          </div>

          {outsideArea ? (
            <Note tone="warn" icon={TriangleAlert}>
              This looks outside Bengaluru South, which is the only area this service covers
              right now. You can still send the report, but it may not reach the right office.
            </Note>
          ) : null}
          {poorAccuracy ? (
            <Note tone="warn" icon={Info}>
              The location is only accurate to about {location.accuracyM} m. Indoors or under
              cover this is common — the landmark below will help more than the pin.
            </Note>
          ) : null}
        </div>
      )}

      {error ? (
        <Note tone="warn" icon={Info}>
          {error}
        </Note>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="landmark" className="text-[1.0625rem] font-semibold text-slate-950">
          ಹತ್ತಿರದ ಗುರುತು · Nearest landmark
        </Label>
        <Input
          id="landmark"
          value={landmark}
          onChange={(event) => onLandmark(event.target.value)}
          maxLength={160}
          placeholder="Opposite Sarakki lake gate, 11th Cross Road"
          className="h-14 rounded-xl border-2 border-slate-300 bg-white px-4 text-base"
        />
        <p className="text-sm leading-6 text-slate-600">
          A shop, a temple, a bus stop — whatever you would tell an auto driver. Please do not
          enter your house number or your name.
        </p>
      </div>
    </div>
  );
}

function Note({
  tone,
  icon: Icon,
  children,
}: {
  tone: "note" | "warn";
  icon: typeof Info;
  children: React.ReactNode;
}) {
  const styles =
    tone === "warn"
      ? "border-lane-statutory-border bg-lane-statutory-surface text-lane-statutory-ink"
      : "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <p className={`mt-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm leading-6 ${styles}`}>
      <Icon className="mt-1 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
