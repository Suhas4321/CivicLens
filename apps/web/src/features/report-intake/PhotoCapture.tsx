import { Camera, ImageUp, Info, MapPin, TriangleAlert, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { distanceMetres, locationBucket, readExif, type ExifReading } from "@/lib/exif";

/**
 * Photo capture for a citizen report: one photo, a preview, and EXIF read
 * client-side purely to tell the reporter what their own file contains.
 *
 * Scope is deliberately narrow — upload, preview, EXIF — per the agreed brief.
 * No vision model, no classification from the image. An officer looks at the
 * photo and judges severity from their desk; that is the whole job it does.
 *
 * **The photo is uploaded unmodified, and that is a decision, not an omission.**
 * Downscaling a 6 MB phone photo before upload would be kind to a metered mobile
 * connection, but re-encoding through a canvas strips EXIF, and EXIF is exactly
 * what the server-side integrity checks read — capture date against submission
 * date, photo location against the reported pin. Losing those to save bandwidth
 * would trade an anti-abuse signal for a smaller request. Instead the file is
 * size-capped, and the reporter is told when a photo is unusually large.
 */

const MAX_BYTES = 12 * 1024 * 1024;
const WARN_BYTES = 6 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];

export type PhotoSelection = {
  file: File;
  exif: ExifReading;
  /** Metres between the photo's own location and the reported pin, when both exist. */
  exifDistanceM?: number;
};

function formatMB(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres / 10) * 10} m` : `${(metres / 1000).toFixed(1)} km`;
}

export function PhotoCapture({
  value,
  onChange,
  pin,
}: {
  value: PhotoSelection | null;
  onChange: (selection: PhotoSelection | null) => void;
  pin: { latitude: number; longitude: number } | null;
}) {
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  // One object URL at a time, revoked whenever it is replaced or the component
  // unmounts. Without this every retake leaks the previous photo's blob.
  useEffect(() => {
    if (!value) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(value.file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [value]);

  async function accept(file: File | undefined) {
    setError(null);
    if (!file) return;

    if (!ACCEPTED.includes(file.type)) {
      setError("That file is not a photo. Please choose a JPG, PNG or HEIC image.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(`That photo is ${formatMB(file.size)}. The limit is ${formatMB(MAX_BYTES)}.`);
      return;
    }

    setReading(true);
    const exif = await readExif(file);
    setReading(false);

    const exifDistanceM =
      pin && exif.latitude !== undefined && exif.longitude !== undefined
        ? distanceMetres(pin, { latitude: exif.latitude, longitude: exif.longitude })
        : undefined;

    onChange({ file, exif, ...(exifDistanceM !== undefined ? { exifDistanceM } : {}) });
  }

  function clear() {
    setError(null);
    onChange(null);
    if (cameraRef.current) cameraRef.current.value = "";
    if (galleryRef.current) galleryRef.current.value = "";
  }

  return (
    <div className="space-y-3">
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        // Opens the rear camera directly on Android and iOS instead of a file
        // browser, which is what someone standing in front of the problem wants.
        capture="environment"
        className="sr-only"
        onChange={(event) => void accept(event.target.files?.[0])}
      />
      <input
        ref={galleryRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(event) => void accept(event.target.files?.[0])}
      />

      {preview && value ? (
        <figure className="overflow-hidden rounded-2xl border-2 border-slate-200 bg-white">
          <div className="relative bg-slate-900">
            <img
              src={preview}
              alt="The photo you attached"
              className="mx-auto max-h-80 w-full object-contain"
            />
            <Button
              type="button"
              variant="secondary"
              onClick={clear}
              className="absolute right-3 top-3 gap-1.5 rounded-full bg-white/95 px-3 shadow-md hover:bg-white"
            >
              <X className="size-4" aria-hidden /> Remove
            </Button>
          </div>

          <figcaption className="space-y-2 p-4 text-sm">
            <p className="numeric text-slate-500">
              {value.file.name} · {formatMB(value.file.size)}
            </p>
            {value.file.size > WARN_BYTES ? (
              <PhotoNote tone="note" icon={Info}>
                This is a large photo and may take a while to send on mobile data.
              </PhotoNote>
            ) : null}
            <ExifNotes selection={value} hasPin={pin !== null} />
          </figcaption>
        </figure>
      ) : (
        <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-5 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-lane-discretionary-surface text-lane-discretionary-ink">
            <Camera className="size-7" aria-hidden />
          </span>
          <p className="mt-3 text-[1.0625rem] font-semibold text-slate-950">
            ಫೋಟೋ ಸೇರಿಸಿ · Add a photo
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm leading-6 text-slate-600">
            A photo lets an officer judge how bad it is without visiting first. Strongly
            recommended, but not required.
          </p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Button
              type="button"
              onClick={() => cameraRef.current?.click()}
              disabled={reading}
              className="gap-2 px-5 text-base"
            >
              <Camera className="size-5" aria-hidden /> Take a photo
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => galleryRef.current?.click()}
              disabled={reading}
              className="gap-2 px-5 text-base"
            >
              <ImageUp className="size-5" aria-hidden /> Choose a photo
            </Button>
          </div>
          {reading ? <p className="mt-3 text-sm text-slate-500">Reading the photo…</p> : null}
        </div>
      )}

      {error ? (
        <PhotoNote tone="warn" icon={TriangleAlert}>
          {error}
        </PhotoNote>
      ) : null}
    </div>
  );
}

function PhotoNote({
  tone,
  icon: Icon,
  children,
}: {
  tone: "note" | "warn" | "good";
  icon: typeof Info;
  children: React.ReactNode;
}) {
  const styles = {
    note: "border-slate-200 bg-slate-50 text-slate-700",
    warn: "border-lane-statutory-border bg-lane-statutory-surface text-lane-statutory-ink",
    good: "border-lane-discretionary-border bg-lane-discretionary-surface text-lane-discretionary-ink",
  }[tone];

  return (
    <p className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm leading-6 ${styles}`}>
      <Icon className="mt-1 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

/**
 * What the photo says about itself, in plain language.
 *
 * The tone matters. A missing photo location is *normal* — WhatsApp and most
 * messaging apps strip it from every image — so it is stated as a neutral fact,
 * not an accusation. Only a genuine mismatch is flagged, and even then the
 * report is still accepted; the officer sees the flag and decides.
 */
function ExifNotes({ selection, hasPin }: { selection: PhotoSelection; hasPin: boolean }) {
  const { exif, exifDistanceM } = selection;
  const notes: React.ReactNode[] = [];

  if (exif.latitude === undefined) {
    notes.push(
      <PhotoNote key="absent" tone="note" icon={Info}>
        This photo carries no location of its own. That is normal — apps like WhatsApp remove
        it. We will use the location you confirm below.
      </PhotoNote>,
    );
  } else if (!hasPin) {
    notes.push(
      <PhotoNote key="pin-first" tone="note" icon={MapPin}>
        This photo has its own location. Confirm where the problem is and we will check that
        the two agree.
      </PhotoNote>,
    );
  } else if (exifDistanceM !== undefined) {
    const bucket = locationBucket(exifDistanceM);
    if (bucket === "match") {
      notes.push(
        <PhotoNote key="match" tone="good" icon={MapPin}>
          The photo was taken at the place you marked.
        </PhotoNote>,
      );
    } else {
      notes.push(
        <PhotoNote key="mismatch" tone="warn" icon={TriangleAlert}>
          The photo was taken about {formatDistance(exifDistanceM)} from the place you marked.
          You can still send it — an officer will see this note.
        </PhotoNote>,
      );
    }
  }

  if (exif.capturedAt) {
    const days = Math.floor((Date.now() - new Date(exif.capturedAt).getTime()) / 86_400_000);
    if (days > 7) {
      notes.push(
        <PhotoNote key="stale" tone="warn" icon={TriangleAlert}>
          This photo was taken about {days} days ago. If the problem is still there, a newer
          photo helps more.
        </PhotoNote>,
      );
    } else if (days < 0) {
      notes.push(
        <PhotoNote key="future" tone="warn" icon={TriangleAlert}>
          This photo is dated in the future, so the camera clock may be wrong.
        </PhotoNote>,
      );
    }
  }

  return notes.length ? <span className="block space-y-2">{notes}</span> : null;
}
