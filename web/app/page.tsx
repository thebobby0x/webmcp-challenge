"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  McpClient,
  McpError,
  resultText,
  toolAgent,
  type InitializeResult,
  type McpTool,
  type ToolResult,
  type WireExchange,
} from "@/lib/mcp";

/** Sensible starting arguments so a judge can click Call without typing. */
const PRESETS: Record<string, Record<string, string>> = {
  // A prefix, not a full address: each exact email owns exactly one meeting,
  // so prefix-matching an attendee cohort is what actually surfaces conflicts.
  bookingagent_detect_conflicts: { attendee_id: "attendee_1" },
  bookingagent_schedule_meeting: { attendee_id: "ATT-0001", meeting_type: "vendor" },
  bookingagent_list_exhibitor_meetings: { exhibitor_id: "exhibitor_3@brand.com" },
  insightagent_analyze_event: { focus: "overall" },
  insightagent_unconfirmed_exhibitors: { region: "EMEA" },
  commsagent_send_notification: {
    attendee_id: "ATT-0001",
    message: "Your 10:00 vendor meeting moved to 10:30, booth B-1042.",
    priority: "high",
  },
  commsagent_escalate_to_human: { issue: "VIP attendee double-booked across two keynotes" },
  commsagent_notification_history: { attendee_id: "ATT-0001" },
  vendoragent_sla_breaches: {},
  complianceagent_check_gdpr: {
    data: '{\n  "name": "Jane Doe",\n  "email": "jane@corp.com",\n  "booth": "B-1042"\n}',
  },
  fleet_list_agents: {},
  fleet_architect_design: {
    event_name: "IMEX America 2026",
    attendees: "12000",
    exhibitors: "3500",
    days: "3",
    features: "badge scanning, VIP concierge, real-time floor routing",
  },
};

type Status = "connecting" | "ready" | "error";

export default function Home() {
  const clientRef = useRef<McpClient | null>(null);

  const [status, setStatus] = useState<Status>("connecting");
  const [handshake, setHandshake] = useState<InitializeResult | null>(null);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [args, setArgs] = useState<Record<string, string>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ToolResult | null>(null);
  const [calling, setCalling] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [upstream, setUpstream] = useState<string | null>(null);
  const [wire, setWire] = useState<WireExchange[]>([]);
  const [openExchange, setOpenExchange] = useState<number | null>(null);

  // ── Connect: initialize, then discover tools ────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const client = new McpClient("/api/mcp", (exchange) =>
      setWire((prev) => [exchange, ...prev].slice(0, 50)),
    );
    clientRef.current = client;

    (async () => {
      try {
        const info = await client.initialize();
        const discovered = await client.listTools();
        if (cancelled) return;

        setHandshake(info);
        setTools(discovered);
        setStatus("ready");
        if (discovered.length > 0) selectTool(discovered[0]);
      } catch (error) {
        if (cancelled) return;
        setStatus("error");
        setBanner(describe(error));
      }
    })();

    fetch("/api/mcp")
      .then((r) => r.json())
      .then((d) => !cancelled && setUpstream(d.upstream))
      .catch(() => undefined);

    return () => {
      cancelled = true;
      void client.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeTool = useMemo(
    () => tools.find((t) => t.name === selected) ?? null,
    [tools, selected],
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, McpTool[]>();
    for (const tool of tools) {
      const agent = toolAgent(tool);
      groups.set(agent, [...(groups.get(agent) ?? []), tool]);
    }
    return [...groups.entries()];
  }, [tools]);

  function selectTool(tool: McpTool) {
    setSelected(tool.name);
    setArgs(PRESETS[tool.name] ?? {});
    setFieldErrors({});
    setResult(null);
    setElapsed(null);
    setBanner(null);
  }

  const call = useCallback(async () => {
    const client = clientRef.current;
    if (!client || !activeTool) return;

    const { values, errors } = buildArguments(activeTool, args);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setCalling(true);
    setBanner(null);
    setResult(null);
    const started = performance.now();

    try {
      const response = await client.callTool(activeTool.name, values);
      setResult(response);
    } catch (error) {
      setBanner(describe(error));
    } finally {
      setElapsed(Math.round(performance.now() - started));
      setCalling(false);
    }
  }, [activeTool, args]);

  return (
    <>
      <header className="header">
        <div className="logo">
          event<span>OS</span> · MCP Console
        </div>
        <div className="header-meta">
          <span className="badge">
            <span className={`dot ${status === "ready" ? "on" : status === "error" ? "err" : "off"}`} />
            {status === "ready" ? "connected" : status === "error" ? "disconnected" : "connecting"}
          </span>
          {handshake && <span className="badge rosa">MCP {handshake.protocolVersion}</span>}
          <span className="badge amber">IMEX America · Oct 12–15 2026</span>
        </div>
      </header>

      <main className="main">
        <section className="intro">
          <h1>A five-agent event fleet, spoken to over MCP</h1>
          <p>
            This page is a Model Context Protocol client. It ran{" "}
            <code>initialize</code> against the eventOS Agent Fleet on Cloud Run,
            discovered its tools with <code>tools/list</code>, and every button below
            issues a real <code>tools/call</code> over JSON-RPC 2.0. Nothing here is
            mocked — the fleet is the same service that runs the event.
          </p>
        </section>

        <div className="conn">
          <div className="conn-field">
            <span className="conn-label">Server</span>
            <span className="conn-value accent">
              {handshake ? `${handshake.serverInfo.name} v${handshake.serverInfo.version}` : "—"}
            </span>
          </div>
          <div className="conn-field">
            <span className="conn-label">Protocol</span>
            <span className="conn-value">{handshake?.protocolVersion ?? "—"}</span>
          </div>
          <div className="conn-field">
            <span className="conn-label">Tools discovered</span>
            <span className="conn-value">{tools.length || "—"}</span>
          </div>
          <div className="conn-spacer" />
          <div className="conn-field">
            <span className="conn-label">Endpoint</span>
            <span className="conn-value">{upstream ?? "/api/mcp"}</span>
          </div>
        </div>

        {banner && <div className="banner">{banner}</div>}

        <div className="columns">
          <aside className="panel">
            <div className="panel-head">
              <span className="panel-title">tools/list</span>
              <span className="badge dim">{tools.length}</span>
            </div>
            {status === "connecting" && <div className="empty"><span className="spinner" />Handshaking…</div>}
            {status === "error" && <div className="empty">Could not reach the fleet.</div>}
            {grouped.map(([agent, agentTools]) => (
              <div className="agent-group" key={agent}>
                <div className="agent-group-label">{agent}</div>
                {agentTools.map((tool) => (
                  <button
                    key={tool.name}
                    className={`tool-item${tool.name === selected ? " selected" : ""}`}
                    onClick={() => selectTool(tool)}
                  >
                    <div className="tool-item-name">{tool.name}</div>
                    <div className="tool-item-title">{tool.title ?? ""}</div>
                  </button>
                ))}
              </div>
            ))}
          </aside>

          <section style={{ display: "grid", gap: 22 }}>
            <div className="panel">
              <div className="panel-head">
                <span className="panel-title">tools/call</span>
                {activeTool && <span className="badge dim">{toolAgent(activeTool)}</span>}
              </div>
              <div className="panel-body">
                {!activeTool && <div className="empty">Select a tool to inspect its schema.</div>}
                {activeTool && (
                  <>
                    <div className="tool-name">{activeTool.name}</div>
                    <p className="tool-desc">{activeTool.description}</p>

                    <ArgumentForm
                      tool={activeTool}
                      values={args}
                      errors={fieldErrors}
                      onChange={(key, value) => setArgs((prev) => ({ ...prev, [key]: value }))}
                    />

                    <div className="actions">
                      <button className="btn" onClick={call} disabled={calling || status !== "ready"}>
                        {calling ? <><span className="spinner" />Calling…</> : "Call tool"}
                      </button>
                      <button
                        className="btn ghost"
                        onClick={() => selectTool(activeTool)}
                        disabled={calling}
                      >
                        Reset
                      </button>
                      {elapsed !== null && !calling && <span className="hint">{elapsed} ms round trip</span>}
                      {activeTool.name === "fleet_architect_design" && !calling && (
                        <span className="hint">live LLM call · expect 15–30s</span>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <span className="panel-title">Result</span>
                {result && (
                  <span className={`badge ${result.isError ? "amber" : ""}`}>
                    {result.isError ? "isError: true" : "ok"}
                  </span>
                )}
              </div>
              <div className="panel-body">
                {!result && !calling && (
                  <div className="empty">
                    No call yet.
                    <br />
                    Pick a tool and hit <strong>Call tool</strong> to see the fleet respond.
                  </div>
                )}
                {calling && <div className="empty"><span className="spinner" />Waiting on the fleet…</div>}
                {result && !calling && (
                  <>
                    <div className="section-label">content[] · what a model reads</div>
                    <div className={`result-summary${result.isError ? " error" : ""}`}>
                      {resultText(result) || "(no text content)"}
                    </div>
                    {result.structuredContent !== undefined && (
                      <>
                        <div className="section-label">structuredContent · machine-readable payload</div>
                        <pre className="json">{JSON.stringify(result.structuredContent, null, 2)}</pre>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <span className="panel-title">JSON-RPC wire log</span>
                <span className="badge dim">{wire.length}</span>
              </div>
              <div className="panel-body">
                {wire.length === 0 && (
                  <div className="empty">Every message this page exchanges with the fleet appears here.</div>
                )}
                {wire.map((exchange) => (
                  <div className="wire" key={exchange.seq}>
                    <button
                      className="wire-head"
                      onClick={() =>
                        setOpenExchange(openExchange === exchange.seq ? null : exchange.seq)
                      }
                    >
                      <span className={`wire-status ${exchange.status}`} />
                      <span className="wire-method">{exchange.method}</span>
                      <span className="wire-spacer" />
                      <span className="wire-ms">{exchange.ms} ms</span>
                      <span className="wire-at">{exchange.at}</span>
                      <span className="wire-caret">{openExchange === exchange.seq ? "−" : "+"}</span>
                    </button>
                    {openExchange === exchange.seq && (
                      <div className="wire-body">
                        <div className="section-label">→ request</div>
                        <pre className="json">{JSON.stringify(exchange.request, null, 2)}</pre>
                        <div className="section-label">← response</div>
                        <pre className="json">
                          {typeof exchange.response === "string"
                            ? exchange.response
                            : JSON.stringify(exchange.response, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      </main>

      <footer className="footer">
        eventOS Agent Fleet · MCP over Streamable HTTP ·{" "}
        <a href={upstream?.replace("/mcp", "/mcp/manifest") ?? "#"} target="_blank" rel="noreferrer">
          tool manifest
        </a>
      </footer>
    </>
  );
}

// ── Argument form ─────────────────────────────────────────────────────────

function ArgumentForm({
  tool,
  values,
  errors,
  onChange,
}: {
  tool: McpTool;
  values: Record<string, string>;
  errors: Record<string, string>;
  onChange: (key: string, value: string) => void;
}) {
  const properties = tool.inputSchema.properties ?? {};
  const required = new Set(tool.inputSchema.required ?? []);
  const names = Object.keys(properties);

  if (names.length === 0) {
    return <p className="no-args">This tool takes no arguments.</p>;
  }

  return (
    <div>
      {names.map((name) => {
        const schema = properties[name];
        const value = values[name] ?? "";
        const error = errors[name];
        const isObject = schema.type === "object";

        return (
          <div className="field" key={name}>
            <div className="field-head">
              <span className="field-name">{name}</span>
              <span className="field-type">
                {schema.type === "array" ? "string[]" : schema.type ?? "any"}
              </span>
              {required.has(name) && <span className="field-req">required</span>}
            </div>
            {schema.description && <div className="field-desc">{schema.description}</div>}

            {schema.enum ? (
              <select
                className="select"
                value={value}
                onChange={(e) => onChange(name, e.target.value)}
              >
                <option value="">— not set —</option>
                {schema.enum.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : isObject ? (
              <textarea
                className={`textarea${error ? " invalid" : ""}`}
                value={value}
                placeholder='{ "field": "value" }'
                onChange={(e) => onChange(name, e.target.value)}
              />
            ) : (
              <input
                className={`input${error ? " invalid" : ""}`}
                value={value}
                placeholder={placeholderFor(schema.type)}
                onChange={(e) => onChange(name, e.target.value)}
              />
            )}

            {error && <div className="field-error">{error}</div>}
          </div>
        );
      })}
    </div>
  );
}

function placeholderFor(type?: string): string {
  if (type === "integer" || type === "number") return "0";
  if (type === "array") return "comma, separated, values";
  return "";
}

/**
 * Turn the form's strings into typed JSON-RPC arguments, coercing each field to
 * the type its schema declares. Blank optional fields are dropped rather than
 * sent as empty strings, so the server applies its own defaults.
 */
function buildArguments(
  tool: McpTool,
  raw: Record<string, string>,
): { values: Record<string, unknown>; errors: Record<string, string> } {
  const properties = tool.inputSchema.properties ?? {};
  const required = new Set(tool.inputSchema.required ?? []);
  const values: Record<string, unknown> = {};
  const errors: Record<string, string> = {};

  for (const [name, schema] of Object.entries(properties)) {
    const text = (raw[name] ?? "").trim();

    if (!text) {
      if (required.has(name)) errors[name] = "Required.";
      continue;
    }

    switch (schema.type) {
      case "integer":
      case "number": {
        const parsed = Number(text);
        if (!Number.isFinite(parsed)) {
          errors[name] = "Must be a number.";
        } else {
          values[name] = schema.type === "integer" ? Math.trunc(parsed) : parsed;
        }
        break;
      }
      case "boolean":
        values[name] = text.toLowerCase() === "true";
        break;
      case "array":
        values[name] = text.split(",").map((v) => v.trim()).filter(Boolean);
        break;
      case "object":
        try {
          const parsed = JSON.parse(text);
          if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
            errors[name] = "Must be a JSON object.";
          } else {
            values[name] = parsed;
          }
        } catch {
          errors[name] = "Not valid JSON.";
        }
        break;
      default:
        values[name] = text;
    }
  }

  return { values, errors };
}

function describe(error: unknown): string {
  if (error instanceof McpError) return `MCP error ${error.code}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return String(error);
}
