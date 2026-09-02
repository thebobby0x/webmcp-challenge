/**
 * eventOS reference data — the catalog half of the WebMCP tool surface.
 *
 * Three of the six browser tools answer from the live agent fleet on Cloud Run
 * (see lib/webmcp-tools.ts). The rest answer from here: the event catalog, the
 * venueSource registry, the planner directory and the per-event financial
 * model. Every tool result labels which of the two it came from in a `source`
 * field, so an agent — or a judge — can tell modeled numbers from live ones.
 */

export interface EventRecord {
  event_id: string;
  name: string;
  starts: string;
  ends: string;
  venue: string;
  city: string;
  attendees: number;
  exhibitors: number;
  status: "planning" | "confirmed" | "live" | "closed";
  track: string;
}

export interface VenueRecord {
  venue_id: string;
  name: string;
  city: string;
  country: string;
  halls: number;
  gross_sqm: number;
  max_capacity: number;
  loading_docks: number;
  power_amps: number;
  wifi_concurrent: number;
  contact: string;
  notes: string;
}

export interface PlannerRecord {
  planner_id: string;
  name: string;
  title: string;
  agency: string;
  city: string;
  specialties: string[];
  events_run: number;
  largest_event: number;
  rating: number;
  languages: string[];
}

/** Upcoming and in-flight events on the eventOS tenant. */
export const EVENTS: EventRecord[] = [
  {
    event_id: "EVT-IMEX-26",
    name: "IMEX America 2026",
    starts: "2026-10-13",
    ends: "2026-10-15",
    venue: "Mandalay Bay Convention Center",
    city: "Las Vegas, NV",
    attendees: 300,
    exhibitors: 200,
    status: "confirmed",
    track: "Business events / MICE",
  },
  {
    event_id: "EVT-WEBSUMMIT-26",
    name: "Web Summit Lisbon 2026",
    starts: "2026-11-09",
    ends: "2026-11-12",
    venue: "Altice Arena",
    city: "Lisbon, PT",
    attendees: 71000,
    exhibitors: 2400,
    status: "planning",
    track: "Technology",
  },
  {
    event_id: "EVT-CES-27",
    name: "CES 2027",
    starts: "2027-01-06",
    ends: "2027-01-09",
    venue: "Las Vegas Convention Center",
    city: "Las Vegas, NV",
    attendees: 138000,
    exhibitors: 4300,
    status: "planning",
    track: "Consumer technology",
  },
  {
    event_id: "EVT-MWC-27",
    name: "MWC Barcelona 2027",
    starts: "2027-03-01",
    ends: "2027-03-04",
    venue: "Fira Gran Via",
    city: "Barcelona, ES",
    attendees: 101000,
    exhibitors: 2700,
    status: "planning",
    track: "Telecom",
  },
  {
    event_id: "EVT-STUDIO0X-DEMO",
    name: "studio0x Partner Day",
    starts: "2026-09-24",
    ends: "2026-09-24",
    venue: "Convene 101 Park Ave",
    city: "New York, NY",
    attendees: 180,
    exhibitors: 12,
    status: "confirmed",
    track: "Private / partner",
  },
];

/** venueSource — the venue registry eventOS resolves floor plans against. */
export const VENUE_SOURCE: VenueRecord[] = [
  {
    venue_id: "VEN-MBCC",
    name: "Mandalay Bay Convention Center",
    city: "Las Vegas, NV",
    country: "USA",
    halls: 4,
    gross_sqm: 195_000,
    max_capacity: 26_000,
    loading_docks: 42,
    power_amps: 4_000,
    wifi_concurrent: 30_000,
    contact: "events@mandalaybay.example",
    notes: "Level 2 south hall has the only 12m clear ceiling — book rigging early.",
  },
  {
    venue_id: "VEN-LVCC",
    name: "Las Vegas Convention Center",
    city: "Las Vegas, NV",
    country: "USA",
    halls: 5,
    gross_sqm: 460_000,
    max_capacity: 200_000,
    loading_docks: 128,
    power_amps: 12_000,
    wifi_concurrent: 150_000,
    contact: "sales@lvcva.example",
    notes: "West Hall connects to Central via the Loop; budget 6 min transfer for VIP routing.",
  },
  {
    venue_id: "VEN-FIRA",
    name: "Fira Gran Via",
    city: "Barcelona, ES",
    country: "Spain",
    halls: 8,
    gross_sqm: 240_000,
    max_capacity: 110_000,
    loading_docks: 96,
    power_amps: 9_000,
    wifi_concurrent: 120_000,
    contact: "operations@firabarcelona.example",
    notes: "Halls 1–3 share a single freight spine; stagger vendor load-in windows.",
  },
  {
    venue_id: "VEN-ALTICE",
    name: "Altice Arena",
    city: "Lisbon, PT",
    country: "Portugal",
    halls: 3,
    gross_sqm: 62_000,
    max_capacity: 20_000,
    loading_docks: 18,
    power_amps: 2_500,
    wifi_concurrent: 45_000,
    contact: "producao@alticearena.example",
    notes: "Riverside pavilions are tented — weather contingency is a hard requirement.",
  },
  {
    venue_id: "VEN-CONVENE-101",
    name: "Convene 101 Park Ave",
    city: "New York, NY",
    country: "USA",
    halls: 1,
    gross_sqm: 3_700,
    max_capacity: 400,
    loading_docks: 2,
    power_amps: 400,
    wifi_concurrent: 1_200,
    contact: "101park@convene.example",
    notes: "House AV only — outside vendors need a 10-day waiver.",
  },
];

/** Event planner profiles in the eventOS partner directory. */
export const PLANNERS: PlannerRecord[] = [
  {
    planner_id: "PLN-0001",
    name: "Marisol Reyes",
    title: "Executive Producer",
    agency: "Northlight Events",
    city: "Las Vegas, NV",
    specialties: ["trade shows", "exhibitor operations", "MICE"],
    events_run: 84,
    largest_event: 42_000,
    rating: 4.9,
    languages: ["English", "Spanish"],
  },
  {
    planner_id: "PLN-0002",
    name: "Tomás Ferreira",
    title: "Head of Live Operations",
    agency: "Atlantic Stagecraft",
    city: "Lisbon, PT",
    specialties: ["conferences", "broadcast", "sponsor activations"],
    events_run: 51,
    largest_event: 71_000,
    rating: 4.7,
    languages: ["Portuguese", "English", "Spanish"],
  },
  {
    planner_id: "PLN-0003",
    name: "Aisha Okonkwo",
    title: "Director, Attendee Experience",
    agency: "Meridian Group",
    city: "London, UK",
    specialties: ["VIP concierge", "hospitality", "accessibility"],
    events_run: 63,
    largest_event: 28_000,
    rating: 4.8,
    languages: ["English", "French"],
  },
  {
    planner_id: "PLN-0004",
    name: "Daniel Kwon",
    title: "Technical Director",
    agency: "Vector AV Partners",
    city: "Seoul, KR",
    specialties: ["AV", "rigging", "show control", "conferences"],
    events_run: 97,
    largest_event: 55_000,
    rating: 4.6,
    languages: ["Korean", "English"],
  },
  {
    planner_id: "PLN-0005",
    name: "Ingrid Halvorsen",
    title: "Sustainability Lead",
    agency: "Northlight Events",
    city: "Oslo, NO",
    specialties: ["sustainability", "vendor sourcing", "trade shows"],
    events_run: 38,
    largest_event: 19_000,
    rating: 4.9,
    languages: ["Norwegian", "English", "German"],
  },
  {
    planner_id: "PLN-0006",
    name: "Rafael Duarte",
    title: "Senior Event Manager",
    agency: "Cinta Live",
    city: "São Paulo, BR",
    specialties: ["festivals", "security", "crowd flow"],
    events_run: 72,
    largest_event: 90_000,
    rating: 4.5,
    languages: ["Portuguese", "Spanish", "English"],
  },
];

export interface PnlLine {
  label: string;
  budget: number;
  actual: number;
}

export interface PnlModel {
  currency: string;
  revenue: PnlLine[];
  costs: PnlLine[];
}

/** Per-event financial model. Budget is contracted; actual is booked to date. */
export const PNL: Record<string, PnlModel> = {
  "EVT-IMEX-26": {
    currency: "USD",
    revenue: [
      { label: "Exhibitor booth sales", budget: 2_400_000, actual: 2_512_000 },
      { label: "Attendee registration", budget: 780_000, actual: 741_500 },
      { label: "Sponsorship", budget: 1_150_000, actual: 1_305_000 },
      { label: "Hosted buyer program", budget: 420_000, actual: 398_000 },
    ],
    costs: [
      { label: "Venue and space rental", budget: 1_100_000, actual: 1_118_400 },
      { label: "AV and production", budget: 640_000, actual: 712_300 },
      { label: "F&B and hospitality", budget: 480_000, actual: 463_900 },
      { label: "Marketing and acquisition", budget: 350_000, actual: 341_200 },
      { label: "Staffing and security", budget: 295_000, actual: 318_600 },
      { label: "Logistics and freight", budget: 210_000, actual: 233_500 },
    ],
  },
  "EVT-WEBSUMMIT-26": {
    currency: "EUR",
    revenue: [
      { label: "Attendee registration", budget: 21_300_000, actual: 9_840_000 },
      { label: "Exhibitor and startup packages", budget: 8_600_000, actual: 4_120_000 },
      { label: "Sponsorship", budget: 12_400_000, actual: 6_950_000 },
    ],
    costs: [
      { label: "Venue and space rental", budget: 6_800_000, actual: 3_400_000 },
      { label: "AV and production", budget: 5_200_000, actual: 2_180_000 },
      { label: "F&B and hospitality", budget: 3_900_000, actual: 1_050_000 },
      { label: "Marketing and acquisition", budget: 4_400_000, actual: 3_910_000 },
      { label: "Staffing and security", budget: 3_100_000, actual: 940_000 },
    ],
  },
  "EVT-STUDIO0X-DEMO": {
    currency: "USD",
    revenue: [
      { label: "Partner sponsorship", budget: 120_000, actual: 145_000 },
      { label: "Ticketed workshops", budget: 36_000, actual: 31_500 },
    ],
    costs: [
      { label: "Venue and space rental", budget: 48_000, actual: 48_000 },
      { label: "AV and production", budget: 22_000, actual: 19_400 },
      { label: "F&B and hospitality", budget: 31_000, actual: 34_800 },
      { label: "Staffing", budget: 14_000, actual: 12_600 },
    ],
  },
};

/** Case-insensitive contains, used by the fuzzy lookups. */
export function matches(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.toLowerCase().trim());
}
