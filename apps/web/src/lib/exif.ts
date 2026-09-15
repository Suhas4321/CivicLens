/**
 * Minimal client-side EXIF reader: GPS position and original capture time only.
 *
 * Why hand-written rather than a dependency: those two tags are all this product
 * uses, and a general-purpose EXIF library brings a parser for several hundred
 * more across formats we never accept. This is about 150 lines and its failure
 * mode is understood — anything it cannot parse returns `{}`, which the caller
 * treats exactly like a photo that never had EXIF.
 *
 * Privacy. This runs in the browser purely to *show the reporter what their own
 * photo contains* before they send it. Raw coordinates are never put in the
 * request body. The authoritative extraction happens server-side from the
 * uploaded file, and per REBUILD_04 the server persists only a bucket
 * (`match` / `near` / `far` / `absent`) plus a distance rounded to the nearest
 * 100 m, then discards the coordinates and strips EXIF from the stored
 * derivative.
 *
 * One thing worth knowing before reading `absent` as suspicious: WhatsApp and
 * most Indian messaging apps strip EXIF from every image they pass on. For this
 * user base a missing location is the common case, not a red flag.
 */

export type ExifReading = {
  latitude?: number;
  longitude?: number;
  /** EXIF DateTimeOriginal, converted to an ISO-8601 string in local time. */
  capturedAt?: string;
};

const JPEG_SOI = 0xffd8;
const APP1 = 0xffe1;
const TIFF_LITTLE_ENDIAN = 0x4949;
const TIFF_BIG_ENDIAN = 0x4d4d;

const TAG_EXIF_IFD = 0x8769;
const TAG_GPS_IFD = 0x8825;
const TAG_DATE_TIME_ORIGINAL = 0x9003;
const TAG_GPS_LAT_REF = 0x0001;
const TAG_GPS_LAT = 0x0002;
const TAG_GPS_LON_REF = 0x0003;
const TAG_GPS_LON = 0x0004;

const TYPE_ASCII = 2;
const TYPE_RATIONAL = 5;

/** EXIF lives near the front of the file, so there is no need to read a 6 MB photo. */
const HEADER_BYTES = 256 * 1024;

type Cursor = { view: DataView; littleEndian: boolean; tiffStart: number };

function u16(cursor: Cursor, offset: number): number {
  return cursor.view.getUint16(offset, cursor.littleEndian);
}

function u32(cursor: Cursor, offset: number): number {
  return cursor.view.getUint32(offset, cursor.littleEndian);
}

/** An EXIF rational is two 32-bit integers: numerator then denominator. */
function rational(cursor: Cursor, offset: number): number {
  const numerator = u32(cursor, offset);
  const denominator = u32(cursor, offset + 4);
  return denominator === 0 ? 0 : numerator / denominator;
}

/** Locate the TIFF header inside the APP1 segment of a JPEG. */
function findTiffStart(view: DataView): number | null {
  if (view.byteLength < 4 || view.getUint16(0) !== JPEG_SOI) return null;

  let offset = 2;
  while (offset + 4 <= view.byteLength) {
    const marker = view.getUint16(offset);
    const length = view.getUint16(offset + 2);
    if (length < 2) return null;

    if (marker === APP1) {
      const header = offset + 4;
      // The segment must begin with "Exif\0\0"; APP1 is also used by XMP.
      if (
        header + 6 <= view.byteLength &&
        view.getUint32(header) === 0x45786966 &&
        view.getUint16(header + 4) === 0x0000
      ) {
        return header + 6;
      }
    }
    // 0xFFDA starts the compressed image data; EXIF cannot appear after it.
    if (marker === 0xffda) return null;
    offset += 2 + length;
  }
  return null;
}

type Entry = { tag: number; type: number; count: number; valueOffset: number };

function readIfd(cursor: Cursor, ifdOffset: number): Entry[] {
  const base = cursor.tiffStart + ifdOffset;
  if (base + 2 > cursor.view.byteLength) return [];

  const count = u16(cursor, base);
  const entries: Entry[] = [];
  for (let index = 0; index < count; index += 1) {
    const entry = base + 2 + index * 12;
    if (entry + 12 > cursor.view.byteLength) break;
    entries.push({
      tag: u16(cursor, entry),
      type: u16(cursor, entry + 2),
      count: u32(cursor, entry + 4),
      // A value of four bytes or fewer is stored inline; anything larger is a
      // pointer, relative to the TIFF header rather than the file.
      valueOffset: entry + 8,
    });
  }
  return entries;
}

function valueAddress(cursor: Cursor, entry: Entry, bytesPerComponent: number): number {
  const size = bytesPerComponent * entry.count;
  return size <= 4 ? entry.valueOffset : cursor.tiffStart + u32(cursor, entry.valueOffset);
}

function readAscii(cursor: Cursor, entry: Entry): string | undefined {
  if (entry.type !== TYPE_ASCII) return undefined;
  const start = valueAddress(cursor, entry, 1);
  if (start + entry.count > cursor.view.byteLength) return undefined;

  let text = "";
  for (let index = 0; index < entry.count; index += 1) {
    const code = cursor.view.getUint8(start + index);
    if (code === 0) break;
    text += String.fromCharCode(code);
  }
  return text;
}

/** Three rationals — degrees, minutes, seconds — collapsed to decimal degrees. */
function readCoordinate(cursor: Cursor, entry: Entry): number | undefined {
  if (entry.type !== TYPE_RATIONAL || entry.count < 3) return undefined;
  const start = valueAddress(cursor, entry, 8);
  if (start + 24 > cursor.view.byteLength) return undefined;

  const degrees = rational(cursor, start);
  const minutes = rational(cursor, start + 8);
  const seconds = rational(cursor, start + 16);
  return degrees + minutes / 60 + seconds / 3600;
}

/** "2026:09:15 07:42:11" is EXIF's own format and is not ISO-8601. */
function parseExifDate(raw: string): string | undefined {
  const match = /^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/.exec(raw.trim());
  if (!match) return undefined;
  const [, year, month, day, hour, minute, second] = match;
  const date = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

export async function readExif(file: Blob): Promise<ExifReading> {
  try {
    const buffer = await file.slice(0, HEADER_BYTES).arrayBuffer();
    const view = new DataView(buffer);
    const tiffStart = findTiffStart(view);
    if (tiffStart === null) return {};

    const byteOrder = view.getUint16(tiffStart);
    if (byteOrder !== TIFF_LITTLE_ENDIAN && byteOrder !== TIFF_BIG_ENDIAN) return {};
    const cursor: Cursor = {
      view,
      littleEndian: byteOrder === TIFF_LITTLE_ENDIAN,
      tiffStart,
    };

    const ifd0 = readIfd(cursor, u32(cursor, tiffStart + 4));
    const reading: ExifReading = {};

    const exifPointer = ifd0.find((entry) => entry.tag === TAG_EXIF_IFD);
    if (exifPointer) {
      const exifIfd = readIfd(cursor, u32(cursor, exifPointer.valueOffset));
      const dateEntry = exifIfd.find((entry) => entry.tag === TAG_DATE_TIME_ORIGINAL);
      if (dateEntry) {
        const raw = readAscii(cursor, dateEntry);
        if (raw) reading.capturedAt = parseExifDate(raw);
      }
    }

    const gpsPointer = ifd0.find((entry) => entry.tag === TAG_GPS_IFD);
    if (gpsPointer) {
      const gpsIfd = readIfd(cursor, u32(cursor, gpsPointer.valueOffset));
      const byTag = new Map(gpsIfd.map((entry) => [entry.tag, entry]));

      const latEntry = byTag.get(TAG_GPS_LAT);
      const lonEntry = byTag.get(TAG_GPS_LON);
      const latRefEntry = byTag.get(TAG_GPS_LAT_REF);
      const lonRefEntry = byTag.get(TAG_GPS_LON_REF);

      if (latEntry && lonEntry) {
        const latitude = readCoordinate(cursor, latEntry);
        const longitude = readCoordinate(cursor, lonEntry);
        const latRef = latRefEntry ? readAscii(cursor, latRefEntry) : "N";
        const lonRef = lonRefEntry ? readAscii(cursor, lonRefEntry) : "E";

        if (latitude !== undefined && longitude !== undefined) {
          reading.latitude = latRef === "S" ? -latitude : latitude;
          reading.longitude = lonRef === "W" ? -longitude : longitude;
        }
      }
    }

    return reading;
  } catch {
    // A truncated, non-JPEG or otherwise unreadable file is indistinguishable
    // from one with no EXIF, and both are handled the same way downstream.
    return {};
  }
}

/** Great-circle distance in metres. Used only to describe a photo to its own sender. */
export function distanceMetres(
  from: { latitude: number; longitude: number },
  to: { latitude: number; longitude: number },
): number {
  const earthRadius = 6_371_000;
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
  const dLat = toRadians(to.latitude - from.latitude);
  const dLon = toRadians(to.longitude - from.longitude);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(from.latitude)) *
      Math.cos(toRadians(to.latitude)) *
      Math.sin(dLon / 2) ** 2;
  return 2 * earthRadius * Math.asin(Math.min(1, Math.sqrt(a)));
}

export type ExifLocationBucket = "match" | "near" | "far" | "absent";

/** REBUILD_04: the only location fact ever persisted from a photo. */
export function locationBucket(distance: number | undefined): ExifLocationBucket {
  if (distance === undefined) return "absent";
  if (distance < 100) return "match";
  if (distance <= 1000) return "near";
  return "far";
}
