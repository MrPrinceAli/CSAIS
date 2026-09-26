/** Koordinat negara yang dikenali ekstraksi lokasi V0.3 (kunci = nama lokasi huruf kecil). */
export type Country = { lat: number; lng: number; label: string; iso: string };

export const COUNTRY: Record<string, Country> = {
  indonesia: { lat: -2.5, lng: 118.0, label: "Indonesia", iso: "ID" },
  singapore: { lat: 1.35, lng: 103.8, label: "Singapura", iso: "SG" },
  malaysia: { lat: 4.2, lng: 101.9, label: "Malaysia", iso: "MY" },
  thailand: { lat: 15.8, lng: 100.9, label: "Thailand", iso: "TH" },
  vietnam: { lat: 14.0, lng: 108.0, label: "Vietnam", iso: "VN" },
  philippines: { lat: 12.9, lng: 121.8, label: "Filipina", iso: "PH" },
  india: { lat: 20.6, lng: 79.0, label: "India", iso: "IN" },
  china: { lat: 35.9, lng: 104.2, label: "Tiongkok", iso: "CN" },
  japan: { lat: 36.2, lng: 138.3, label: "Jepang", iso: "JP" },
  "south korea": { lat: 35.9, lng: 127.8, label: "Korea Selatan", iso: "KR" },
  australia: { lat: -25.3, lng: 133.8, label: "Australia", iso: "AU" },
  "united states": { lat: 37.1, lng: -95.7, label: "Amerika Serikat", iso: "US" },
  "united kingdom": { lat: 55.4, lng: -3.4, label: "Inggris", iso: "GB" },
  germany: { lat: 51.2, lng: 10.4, label: "Jerman", iso: "DE" },
  france: { lat: 46.2, lng: 2.2, label: "Prancis", iso: "FR" },
  russia: { lat: 61.5, lng: 105.3, label: "Rusia", iso: "RU" },
  ukraine: { lat: 48.4, lng: 31.2, label: "Ukraina", iso: "UA" },
  canada: { lat: 56.1, lng: -106.3, label: "Kanada", iso: "CA" },
  brazil: { lat: -14.2, lng: -51.9, label: "Brasil", iso: "BR" },
  "north korea": { lat: 40.3, lng: 127.5, label: "Korea Utara", iso: "KP" },
  iran: { lat: 32.4, lng: 53.7, label: "Iran", iso: "IR" },
  israel: { lat: 31.0, lng: 34.9, label: "Israel", iso: "IL" },
  taiwan: { lat: 23.7, lng: 121.0, label: "Taiwan", iso: "TW" },
  netherlands: { lat: 52.1, lng: 5.3, label: "Belanda", iso: "NL" },
  "hong kong": { lat: 22.3, lng: 114.2, label: "Hong Kong", iso: "HK" },
  pakistan: { lat: 30.4, lng: 69.3, label: "Pakistan", iso: "PK" },
  bangladesh: { lat: 23.7, lng: 90.4, label: "Bangladesh", iso: "BD" },
  "sri lanka": { lat: 7.9, lng: 80.8, label: "Sri Lanka", iso: "LK" },
  myanmar: { lat: 21.9, lng: 95.9, label: "Myanmar", iso: "MM" },
  cambodia: { lat: 12.6, lng: 104.9, label: "Kamboja", iso: "KH" },
  "saudi arabia": { lat: 23.9, lng: 45.1, label: "Arab Saudi", iso: "SA" },
  "united arab emirates": { lat: 23.4, lng: 53.8, label: "Uni Emirat Arab", iso: "AE" },
  turkey: { lat: 39.0, lng: 35.2, label: "Turki", iso: "TR" },
  egypt: { lat: 26.8, lng: 30.8, label: "Mesir", iso: "EG" },
  nigeria: { lat: 9.1, lng: 8.7, label: "Nigeria", iso: "NG" },
  "south africa": { lat: -30.6, lng: 22.9, label: "Afrika Selatan", iso: "ZA" },
  mexico: { lat: 23.6, lng: -102.6, label: "Meksiko", iso: "MX" },
  argentina: { lat: -38.4, lng: -63.6, label: "Argentina", iso: "AR" },
  italy: { lat: 41.9, lng: 12.6, label: "Italia", iso: "IT" },
  spain: { lat: 40.5, lng: -3.7, label: "Spanyol", iso: "ES" },
  poland: { lat: 51.9, lng: 19.1, label: "Polandia", iso: "PL" },
  sweden: { lat: 60.1, lng: 18.6, label: "Swedia", iso: "SE" },
  switzerland: { lat: 46.8, lng: 8.2, label: "Swiss", iso: "CH" },
  belgium: { lat: 50.5, lng: 4.5, label: "Belgia", iso: "BE" },
  "new zealand": { lat: -40.9, lng: 174.9, label: "Selandia Baru", iso: "NZ" },
  colombia: { lat: 4.6, lng: -74.3, label: "Kolombia", iso: "CO" },
};

export function countryOf(location: string | null | undefined): Country | null {
  if (!location) return null;
  const key = location.split(",")[0].trim().toLowerCase();
  return COUNTRY[key] ?? null;
}

const ISO_LABEL: Record<string, string> = Object.fromEntries(Object.values(COUNTRY).map((c) => [c.iso, c.label]));
ISO_LABEL.ZA = "Afrika Selatan";
ISO_LABEL.NL = "Belanda";
ISO_LABEL.NZ = "Selandia Baru";
ISO_LABEL.IE = "Irlandia";
ISO_LABEL.CH = "Swiss";
ISO_LABEL.SE = "Swedia";
ISO_LABEL.IL = "Israel";
ISO_LABEL.AE = "Uni Emirat Arab";
ISO_LABEL.PK = "Pakistan";
ISO_LABEL.NG = "Nigeria";

export function isoLabel(code: string | null | undefined): string {
  if (!code || code === "unknown") return "tidak diketahui";
  return ISO_LABEL[code.toUpperCase()] ?? code.toUpperCase();
}
