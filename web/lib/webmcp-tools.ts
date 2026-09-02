/**
 * The six eventOS tools this page publishes to any agent driving the browser.
 *
 * These are WebMCP tools, not server MCP tools: they are registered on
 * `document.modelContext` by app/webmcp-provider.tsx and run *in the tab*, with
 * the user's session, on the page the user is already looking at. Nothing here
 * needs an API key, an OAuth grant, or a server the agent has to be told about.
 *
 * Three of them (get_event_sentiment, list_events, check_vendor_status) answer
 * from the live eventOS Agent Fleet over MCP via /api/mcp; the other three
 * answer from the local catalog in lib/event-source.ts. Every result declares
 * which in a `source` field so an agent never mistakes a modeled number for a
 * measured one.
 */

import { McpClient } from "@/lib/mcp";
import {
  EVENTS,
  PLANNERS,
  PNL,
  VENUE_SOURCE,
  matches,
  type EventRecord,
  type PnlLine,
} from "@/lib/event-source";

/* ── WebMCP surface types ─────────────────────────────────────────────── */

export interface ContentBlock {
  type: "text";
  text: string;
}

/** What a WebMCP `execute` resolves to, per the spec's CallToolResult shape. */
export interface WebMcpResult {
  content: ContentBlock[];
  structuredContent?: unknown;
  isError?: boolean;
}

export interface WebMcpToolDescriptor {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<
      string,
      { type: string; description: string; enum?: string[]; default?: unknown }
    >;
    required?: string[];
  };
  execute: (input: Record<string, unknown>) => Promise<WebMcpResult>;
}

/** Extra metadata the landing page uses to render each tool. Not sent to hosts. */
export interface ToolCard {
  name: string;
  headline: string;
  backing: "live" | "catalog";
  sample: Record<string, string>;
}

/* ── Live fleet access ────────────────────────────────────────────────── */

/**
 * One MCP session shared by every live-backed tool. The handshake is expensive
 * relative to a tool call, so it is done once and awaited by later callers.
 */
let sessionPromise: Promise<McpClient> | null = null;

function fleet(): Promise<McpClient> {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const client = new McpClient("/api/mcp");
      await client.initialize();
      return client;
    })().catch((error) => {
      // Do not cache a failed handshake — the next call should retry.
      sessionPromise = null;
      throw error;
    });
  }
  return sessionPromise;
}

/** Call a fleet tool and hand back its structuredContent, typed by the caller. */
async function callFleet<T>(name: string, args: Record<string, unknown> = {}): Promise<T> {
  const client = await fleet();
  const result = await client.callTool(name, args);
  if (result.isError) {
    throw new Error(`Fleet tool ${name} reported an error`);
  }
  return result.structuredContent as T;
}

/* ── Result helpers ───────────────────────────────────────────────────── */

/**
 * Agents read the text block; well-behaved hosts also read structuredContent.
 * Sending the same payload as both means neither has to guess.
 */
function ok(summary: string, data: Record<string, unknown>): WebMcpResult {
  return {
    content: [{ type: "text", text: `${summary}\n\n${JSON.stringify(data, null, 2)}` }],
    structuredContent: data,
  };
}

/**
 * Failures come back as a normal result with isError, not a thrown exception —
 * an agent can read and recover from this, where a rejection just dead-ends.
 */
function fail(message: string, hint?: string): WebMcpResult {
  const payload = { ok: false, error: message, ...(hint ? { hint } : {}) };
  return {
    content: [{ type: "text", text: `${message}${hint ? `\n\n${hint}` : ""}` }],
    structuredContent: payload,
    isError: true,
  };
}

function str(input: Record<string, unknown>, key: string): string {
  const value = input?.[key];
  return typeof value === "string" ? value.trim() : "";
}

function money(value: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function resolveEvent(idOrName: string): EventRecord | undefined {
  return (
    EVENTS.find((event) => event.event_id.toLowerCase() === idOrName.toLowerCase()) ??
    EVENTS.find((event) => matches(event.name, idOrName) || matches(event.event_id, idOrName))
  );
}

const KNOWN_EVENT_IDS = EVENTS.map((event) => event.event_id).join(", ");

/** The one event the live fleet actually holds data for. */
const LIVE_EVENT_ID = "EVT-IMEX-26";

/* ── Live fleet payload shapes ────────────────────────────────────────── */

interface AnalyzeEventResult {
  headline: string;
  kpis: {
    total_meetings: number;
    confirmed_meetings: number;
    confirmation_rate_pct: number;
    total_exhibitors: number;
    unconfirmed_exhibitors: number;
    total_attendees: number;
    vip_attendees: number;
    vendor_at_risk: number;
    at_risk_vendors: string[];
    timestamp: string;
  };
  recommendations: string[];
}

interface SlaBreachResult {
  breach_count: number;
  tracked_vendors: number;
  vendors: {
    id: string;
    name: string;
    type: string;
    deliverable: string;
    due: string;
    status: string;
  }[];
}

interface UnconfirmedExhibitorsResult {
  /** Full count. `exhibitors` is a page of it — the fleet caps that list at 25. */
  total?: number;
  region?: string | null;
  exhibitors?: {
    id?: string;
    company?: string;
    booth?: string;
    category?: string;
    region?: string;
    setup_confirmed?: boolean;
  }[];
}

/* ── Tool 1: get_event_sentiment ──────────────────────────────────────── */

/**
 * Sentiment here is *operational*, not survey-based: it is scored from the live
 * KPIs the fleet reports — confirmation rate, exhibitor readiness, vendor SLA
 * risk. The result says so in `method`, because an agent quoting these numbers
 * to a stakeholder needs to know they are derived signal rather than a poll.
 */
const getEventSentiment: WebMcpToolDescriptor = {
  name: "get_event_sentiment",
  description:
    "Sentiment breakdown for an eventOS event — positive, neutral and negative signal counts plus the top themes driving them. For the live event this is scored from the eventOS agent fleet's real-time KPIs (meeting confirmation rate, exhibitor readiness, vendor SLA risk); for other events it is modeled from the catalog.",
  inputSchema: {
    type: "object",
    properties: {
      event_id: {
        type: "string",
        description: `Event identifier or name fragment, e.g. "EVT-IMEX-26" or "IMEX". Known ids: ${KNOWN_EVENT_IDS}.`,
      },
    },
    required: ["event_id"],
  },
  async execute(input) {
    const query = str(input, "event_id");
    if (!query) return fail("event_id is required.", `Try one of: ${KNOWN_EVENT_IDS}`);

    const event = resolveEvent(query);
    if (!event) {
      return fail(`No event matched "${query}".`, `Known ids: ${KNOWN_EVENT_IDS}`);
    }

    if (event.event_id === LIVE_EVENT_ID) {
      try {
        const live = await callFleet<AnalyzeEventResult>("insightagent_analyze_event", {
          focus: "overall",
          query: "Score attendee and exhibitor sentiment from current operational signals.",
        });

        const k = live.kpis;
        // Each signal is one confirmed meeting, one exhibitor, one vendor. The
        // buckets are counts of real records, not of imagined respondents.
        const positive = k.confirmed_meetings + (k.total_exhibitors - k.unconfirmed_exhibitors);
        const negative = k.vendor_at_risk + k.unconfirmed_exhibitors;
        const neutral = k.total_meetings - k.confirmed_meetings + k.vip_attendees;
        const total = positive + neutral + negative;

        const themes = [
          {
            theme: "Meeting scheduling",
            polarity: k.confirmation_rate_pct >= 95 ? "positive" : "mixed",
            signal_count: k.total_meetings,
            detail: `${k.confirmation_rate_pct}% of ${k.total_meetings} meetings confirmed.`,
          },
          {
            theme: "Vendor reliability",
            polarity: "negative",
            signal_count: k.vendor_at_risk,
            detail: `${k.vendor_at_risk} vendors at risk of or in SLA breach.`,
          },
          {
            theme: "Exhibitor readiness",
            polarity: k.unconfirmed_exhibitors > 0 ? "negative" : "positive",
            signal_count: k.unconfirmed_exhibitors,
            detail: `${k.unconfirmed_exhibitors} of ${k.total_exhibitors} exhibitors have not confirmed booth setup.`,
          },
          {
            theme: "VIP experience",
            polarity: "neutral",
            signal_count: k.vip_attendees,
            detail: `${k.vip_attendees} VIP attendees flagged for concierge handling.`,
          },
        ].sort((a, b) => b.signal_count - a.signal_count);

        const score = total ? Math.round(((positive - negative) / total) * 100) : 0;

        return ok(
          `${event.name}: sentiment score ${score > 0 ? "+" : ""}${score} from ${total} live signals. ${live.headline}`,
          {
            source: "live:eventos-agent-fleet",
            method:
              "Operational sentiment. Each signal is one confirmed meeting, exhibitor record or vendor SLA state pulled live from insightagent_analyze_event — not a survey response.",
            event_id: event.event_id,
            event_name: event.name,
            measured_at: k.timestamp,
            sentiment: { positive, neutral, negative, total, score },
            top_themes: themes,
            headline: live.headline,
            recommendations: live.recommendations,
          },
        );
      } catch (error) {
        return fail(
          `The eventOS agent fleet is unreachable, so live sentiment for ${event.name} is unavailable.`,
          error instanceof Error ? error.message : String(error),
        );
      }
    }

    // Catalog events have no live telemetry; model from scale and status.
    const readiness = { planning: 0.62, confirmed: 0.86, live: 0.91, closed: 0.88 }[event.status];
    const total = Math.round(event.attendees * 0.08) + event.exhibitors;
    const positive = Math.round(total * readiness);
    const negative = Math.round(total * (1 - readiness) * 0.55);
    const neutral = total - positive - negative;

    return ok(
      `${event.name}: modeled sentiment across ${total} projected signals (event is in ${event.status}).`,
      {
        source: "catalog",
        method:
          "Modeled from event scale and lifecycle status. No live telemetry exists for this event yet — only EVT-IMEX-26 is instrumented by the agent fleet.",
        event_id: event.event_id,
        event_name: event.name,
        sentiment: {
          positive,
          neutral,
          negative,
          total,
          score: Math.round(((positive - negative) / total) * 100),
        },
        top_themes: [
          {
            theme: "Pre-registration interest",
            polarity: "positive",
            signal_count: positive,
            detail: `${event.attendees.toLocaleString()} attendees projected across ${event.track}.`,
          },
          {
            theme: "Exhibitor onboarding",
            polarity: event.status === "planning" ? "mixed" : "positive",
            signal_count: event.exhibitors,
            detail: `${event.exhibitors.toLocaleString()} exhibitors in the ${event.status} stage.`,
          },
        ],
      },
    );
  },
};

/* ── Tool 2: list_events ──────────────────────────────────────────────── */

const listEvents: WebMcpToolDescriptor = {
  name: "list_events",
  description:
    "List every upcoming eventOS event with name, dates, venue, attendee count, exhibitor count and lifecycle status. The instrumented event is enriched with live counts from the eventOS agent fleet.",
  inputSchema: { type: "object", properties: {} },
  async execute() {
    let liveKpis: AnalyzeEventResult["kpis"] | null = null;
    try {
      liveKpis = (await callFleet<AnalyzeEventResult>("insightagent_analyze_event", {
        focus: "overall",
      })).kpis;
    } catch {
      // The catalog still answers fully; live enrichment is a bonus, not a
      // dependency, so a fleet outage must not take this tool down.
    }

    const events = EVENTS.map((event) => {
      const live = liveKpis && event.event_id === LIVE_EVENT_ID;
      return {
        event_id: event.event_id,
        name: event.name,
        starts: event.starts,
        ends: event.ends,
        venue: event.venue,
        city: event.city,
        track: event.track,
        status: event.status,
        attendees: live ? liveKpis!.total_attendees : event.attendees,
        exhibitors: live ? liveKpis!.total_exhibitors : event.exhibitors,
        ...(live
          ? {
              live: true,
              scheduled_meetings: liveKpis!.total_meetings,
              vip_attendees: liveKpis!.vip_attendees,
            }
          : { live: false }),
      };
    }).sort((a, b) => a.starts.localeCompare(b.starts));

    return ok(
      `${events.length} events on the eventOS tenant, next up ${events[0].name} on ${events[0].starts}.`,
      {
        source: liveKpis ? "catalog + live:eventos-agent-fleet" : "catalog",
        count: events.length,
        live_event_id: liveKpis ? LIVE_EVENT_ID : null,
        events,
      },
    );
  },
};

/* ── Tool 3: get_event_pnl ────────────────────────────────────────────── */

const getEventPnl: WebMcpToolDescriptor = {
  name: "get_event_pnl",
  description:
    "Profit and loss for an eventOS event — revenue lines, cost lines, gross profit, margin, and budget-versus-actual variance per line with the largest overruns called out.",
  inputSchema: {
    type: "object",
    properties: {
      event_id: {
        type: "string",
        description: `Event identifier or name fragment. Financials exist for: ${Object.keys(PNL).join(", ")}.`,
      },
    },
    required: ["event_id"],
  },
  async execute(input) {
    const query = str(input, "event_id");
    if (!query) return fail("event_id is required.", `Financials exist for: ${Object.keys(PNL).join(", ")}`);

    const event = resolveEvent(query);
    if (!event) return fail(`No event matched "${query}".`, `Known ids: ${KNOWN_EVENT_IDS}`);

    const model = PNL[event.event_id];
    if (!model) {
      return fail(
        `${event.name} has no financial model yet — it is still in ${event.status}.`,
        `Financials exist for: ${Object.keys(PNL).join(", ")}`,
      );
    }

    const withVariance = (line: PnlLine, overIsBad: boolean) => {
      const variance = line.actual - line.budget;
      return {
        label: line.label,
        budget: line.budget,
        actual: line.actual,
        variance,
        variance_pct: Math.round((variance / line.budget) * 1000) / 10,
        // On revenue, over budget is good; on costs, over budget is an overrun.
        favorable: overIsBad ? variance <= 0 : variance >= 0,
      };
    };

    const revenue = model.revenue.map((line) => withVariance(line, false));
    const costs = model.costs.map((line) => withVariance(line, true));

    const sum = (lines: { actual: number; budget: number }[], key: "actual" | "budget") =>
      lines.reduce((total, line) => total + line[key], 0);

    const revenueActual = sum(revenue, "actual");
    const costActual = sum(costs, "actual");
    const profit = revenueActual - costActual;
    const budgetedProfit = sum(revenue, "budget") - sum(costs, "budget");

    const overruns = costs
      .filter((line) => !line.favorable)
      .sort((a, b) => b.variance - a.variance)
      .slice(0, 3)
      .map((line) => `${line.label} ${money(line.variance, model.currency)} over (${line.variance_pct}%)`);

    return ok(
      `${event.name}: ${money(revenueActual, model.currency)} revenue, ${money(costActual, model.currency)} costs, ${money(profit, model.currency)} profit at ${Math.round((profit / revenueActual) * 1000) / 10}% margin.`,
      {
        source: "catalog",
        method: "Contracted budget versus booked-to-date actuals from the eventOS financial model.",
        event_id: event.event_id,
        event_name: event.name,
        currency: model.currency,
        summary: {
          revenue: revenueActual,
          costs: costActual,
          profit,
          margin_pct: Math.round((profit / revenueActual) * 1000) / 10,
          budgeted_profit: budgetedProfit,
          profit_variance: profit - budgetedProfit,
        },
        revenue,
        costs,
        largest_overruns: overruns.length ? overruns : ["No cost line is over budget."],
      },
    );
  },
};

/* ── Tool 4: check_vendor_status ──────────────────────────────────────── */

const checkVendorStatus: WebMcpToolDescriptor = {
  name: "check_vendor_status",
  description:
    "Vendor readiness for an eventOS event — how many vendors are checked in and on track, how many are at risk or already in SLA breach, and how many exhibitor booth approvals are still pending. Live from the eventOS agent fleet's VendorAgent and InsightAgent.",
  inputSchema: {
    type: "object",
    properties: {
      event_id: {
        type: "string",
        description: `Event identifier or name fragment. Live vendor telemetry exists for ${LIVE_EVENT_ID}.`,
      },
    },
    required: ["event_id"],
  },
  async execute(input) {
    const query = str(input, "event_id");
    if (!query) return fail("event_id is required.", `Try ${LIVE_EVENT_ID}.`);

    const event = resolveEvent(query);
    if (!event) return fail(`No event matched "${query}".`, `Known ids: ${KNOWN_EVENT_IDS}`);

    if (event.event_id !== LIVE_EVENT_ID) {
      return fail(
        `${event.name} has no vendor telemetry — it is still in ${event.status}.`,
        `Only ${LIVE_EVENT_ID} is instrumented by the agent fleet.`,
      );
    }

    try {
      const [sla, exhibitors] = await Promise.all([
        callFleet<SlaBreachResult>("vendoragent_sla_breaches", {}),
        callFleet<UnconfirmedExhibitorsResult>("insightagent_unconfirmed_exhibitors", {}),
      ]);

      const onTrack = sla.tracked_vendors - sla.breach_count;
      const byStatus: Record<string, number> = {};
      const byType: Record<string, number> = {};
      for (const vendor of sla.vendors) {
        byStatus[vendor.status] = (byStatus[vendor.status] ?? 0) + 1;
        byType[vendor.type] = (byType[vendor.type] ?? 0) + 1;
      }

      // `total` is the true count; `exhibitors` is only the first page of it.
      const pendingApprovals = exhibitors.total ?? exhibitors.exhibitors?.length ?? 0;

      return ok(
        `${event.name}: ${onTrack} of ${sla.tracked_vendors} vendors checked in and on track, ${sla.breach_count} flagged, ${pendingApprovals} exhibitor approvals pending.`,
        {
          source: "live:eventos-agent-fleet",
          event_id: event.event_id,
          event_name: event.name,
          checked_in: onTrack,
          tracked_vendors: sla.tracked_vendors,
          flagged: sla.breach_count,
          flagged_by_status: byStatus,
          flagged_by_type: byType,
          pending_approvals: pendingApprovals,
          pending_approvals_detail: "Exhibitors that have not confirmed booth setup.",
          pending_approvals_sample: exhibitors.exhibitors?.slice(0, 8) ?? [],
          at_risk_sample: sla.vendors.slice(0, 8),
        },
      );
    } catch (error) {
      return fail(
        "The eventOS agent fleet is unreachable, so vendor status cannot be read.",
        error instanceof Error ? error.message : String(error),
      );
    }
  },
};

/* ── Tool 5: get_venue_info ───────────────────────────────────────────── */

const getVenueInfo: WebMcpToolDescriptor = {
  name: "get_venue_info",
  description:
    "Look up a venue in venueSource, the eventOS venue registry — halls, gross floor area, capacity, loading docks, power and wi-fi headroom, operations contact, and the operational caveat planners need to know.",
  inputSchema: {
    type: "object",
    properties: {
      venue_name: {
        type: "string",
        description:
          'Venue name or fragment, e.g. "Mandalay Bay", "Fira", "Convene". Matched case-insensitively against name and city.',
      },
    },
    required: ["venue_name"],
  },
  async execute(input) {
    const query = str(input, "venue_name");
    if (!query) {
      return fail(
        "venue_name is required.",
        `venueSource holds: ${VENUE_SOURCE.map((v) => v.name).join(", ")}`,
      );
    }

    const hits = VENUE_SOURCE.filter(
      (venue) => matches(venue.name, query) || matches(venue.city, query) || matches(venue.venue_id, query),
    );

    if (!hits.length) {
      return fail(
        `venueSource has no venue matching "${query}".`,
        `Known venues: ${VENUE_SOURCE.map((v) => v.name).join(", ")}`,
      );
    }

    const events = (venueName: string) =>
      EVENTS.filter((event) => event.venue === venueName).map((event) => event.event_id);

    const enriched = hits.map((venue) => ({
      ...venue,
      sqm_per_attendee: Math.round((venue.gross_sqm / venue.max_capacity) * 100) / 100,
      eventos_events: events(venue.name),
    }));

    return ok(
      hits.length === 1
        ? `${hits[0].name}, ${hits[0].city} — ${hits[0].halls} halls, ${hits[0].gross_sqm.toLocaleString()} m², capacity ${hits[0].max_capacity.toLocaleString()}.`
        : `${hits.length} venues in venueSource match "${query}".`,
      { source: "venueSource", query, count: enriched.length, venues: enriched },
    );
  },
};

/* ── Tool 6: search_planners ──────────────────────────────────────────── */

const searchPlanners: WebMcpToolDescriptor = {
  name: "search_planners",
  description:
    "Search the eventOS partner directory for event planners. Matches on name, agency, city, job title, specialty and language, and returns each match ranked by how well it fits the query.",
  inputSchema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description:
          'What to search for — a specialty ("AV", "sustainability"), a city ("Lisbon"), an agency, a language, or a person\'s name.',
      },
    },
    required: ["query"],
  },
  async execute(input) {
    const query = str(input, "query");
    if (!query) return fail("query is required.", 'Try "AV", "Las Vegas", "sustainability" or "trade shows".');

    // Score rather than filter, so a broad query still returns a ranked list
    // instead of an empty one an agent has to guess its way out of.
    const scored = PLANNERS.map((planner) => {
      let score = 0;
      const reasons: string[] = [];

      if (matches(planner.name, query)) { score += 5; reasons.push("name"); }
      if (matches(planner.agency, query)) { score += 4; reasons.push("agency"); }
      if (matches(planner.city, query)) { score += 3; reasons.push("city"); }
      if (matches(planner.title, query)) { score += 2; reasons.push("title"); }
      for (const specialty of planner.specialties) {
        if (matches(specialty, query)) { score += 4; reasons.push(`specialty: ${specialty}`); }
      }
      for (const language of planner.languages) {
        if (matches(language, query)) { score += 2; reasons.push(`language: ${language}`); }
      }

      return { planner, score, reasons };
    })
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score || b.planner.rating - a.planner.rating);

    if (!scored.length) {
      const specialties = [...new Set(PLANNERS.flatMap((p) => p.specialties))].join(", ");
      return fail(`No planner in the directory matched "${query}".`, `Known specialties: ${specialties}`);
    }

    return ok(
      `${scored.length} planner${scored.length === 1 ? "" : "s"} match "${query}", best fit ${scored[0].planner.name} (${scored[0].planner.agency}).`,
      {
        source: "catalog",
        query,
        count: scored.length,
        planners: scored.map(({ planner, score, reasons }) => ({
          ...planner,
          match_score: score,
          matched_on: [...new Set(reasons)],
        })),
      },
    );
  },
};

/* ── Export ───────────────────────────────────────────────────────────── */

export const TOOLS: WebMcpToolDescriptor[] = [
  getEventSentiment,
  listEvents,
  getEventPnl,
  checkVendorStatus,
  getVenueInfo,
  searchPlanners,
];

/** Presentation metadata for the landing page, keyed by tool name. */
export const TOOL_CARDS: Record<string, ToolCard> = {
  get_event_sentiment: {
    name: "get_event_sentiment",
    headline: "Operational sentiment, scored live",
    backing: "live",
    sample: { event_id: "EVT-IMEX-26" },
  },
  list_events: {
    name: "list_events",
    headline: "The event book, with live counts",
    backing: "live",
    sample: {},
  },
  get_event_pnl: {
    name: "get_event_pnl",
    headline: "Revenue, cost and variance",
    backing: "catalog",
    sample: { event_id: "EVT-IMEX-26" },
  },
  check_vendor_status: {
    name: "check_vendor_status",
    headline: "Check-ins, SLA risk, pending approvals",
    backing: "live",
    sample: { event_id: "EVT-IMEX-26" },
  },
  get_venue_info: {
    name: "get_venue_info",
    headline: "venueSource registry lookup",
    backing: "catalog",
    sample: { venue_name: "Mandalay Bay" },
  },
  search_planners: {
    name: "search_planners",
    headline: "Ranked planner directory search",
    backing: "catalog",
    sample: { query: "sustainability" },
  },
};
