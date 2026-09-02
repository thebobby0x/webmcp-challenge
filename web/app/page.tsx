"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { READY_EVENT, type RegistrationStatus } from "@/lib/webmcp";
import {
  TOOLS,
  TOOL_CARDS,
  type WebMcpResult,
  type WebMcpToolDescriptor,
} from "@/lib/webmcp-tools";

const REPO = "https://github.com/thebobby0x/webmcp-challenge";
const CHATGPT = "https://chatgpt.com/";

interface RunState {
  running: boolean;
  ms: number | null;
  result: WebMcpResult | null;
  error: string | null;
}

const IDLE: RunState = { running: false, ms: null, result: null, error: null };

export default function Landing() {
  const [status, setStatus] = useState<RegistrationStatus | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [args, setArgs] = useState<Record<string, Record<string, string>>>({});
  const [runs, setRuns] = useState<Record<string, RunState>>({});

  // The provider in the root layout registers on mount and announces itself.
  // It may well have fired before this component hydrated, so also read the
  // status it parked on `window` rather than waiting on an event that is gone.
  useEffect(() => {
    const adopt = (next: RegistrationStatus) => setStatus(next);
    const listener = (event: Event) => adopt((event as CustomEvent<RegistrationStatus>).detail);

    window.addEventListener(READY_EVENT, listener);
    if (window.__eventosWebMCP) adopt(window.__eventosWebMCP);

    return () => window.removeEventListener(READY_EVENT, listener);
  }, []);

  const argsFor = useCallback(
    (tool: WebMcpToolDescriptor): Record<string, string> =>
      args[tool.name] ?? TOOL_CARDS[tool.name]?.sample ?? {},
    [args],
  );

  const setArg = useCallback(
    (toolName: string, key: string, value: string) =>
      setArgs((prev) => ({
        ...prev,
        [toolName]: { ...(prev[toolName] ?? TOOL_CARDS[toolName]?.sample ?? {}), [key]: value },
      })),
    [],
  );

  const run = useCallback(
    async (tool: WebMcpToolDescriptor) => {
      setRuns((prev) => ({ ...prev, [tool.name]: { ...IDLE, running: true } }));
      const started = performance.now();
      try {
        // Deliberately routed through the registered surface rather than the
        // imported function: this exercises the same path an agent would take.
        const caller = window.__eventosWebMCP?.call;
        const result = caller
          ? await caller(tool.name, argsFor(tool))
          : await tool.execute(argsFor(tool));

        setRuns((prev) => ({
          ...prev,
          [tool.name]: { running: false, ms: Math.round(performance.now() - started), result, error: null },
        }));
      } catch (error) {
        setRuns((prev) => ({
          ...prev,
          [tool.name]: {
            running: false,
            ms: Math.round(performance.now() - started),
            result: null,
            error: error instanceof Error ? error.message : String(error),
          },
        }));
      }
    },
    [argsFor],
  );

  const liveCount = useMemo(
    () => TOOLS.filter((tool) => TOOL_CARDS[tool.name]?.backing === "live").length,
    [],
  );

  return (
    <>
      <header className="header">
        <div className="logo">
          event<span>OS</span> · WebMCP
        </div>
        <div className="header-meta">
          <span className="badge">
            <span className={`dot ${status ? "on" : "off"}`} />
            {status ? `${status.registered.length} tools registered` : "registering…"}
          </span>
          {status && (
            <span className={`badge ${status.native ? "rosa" : "dim"}`}>
              {status.native ? status.surfaces[0] : "no WebMCP host — shim active"}
            </span>
          )}
          <a className="badge amber link-badge" href="/console">
            MCP console →
          </a>
        </div>
      </header>

      <main className="main">
        <section className="hero">
          <div className="hero-copy">
          <p className="eyebrow">WebMCP Challenge · browser-native tool calling</p>
          <h1>
            The event operations stack, <span className="accent">callable from the tab</span>.
          </h1>
          <p className="lede">
            eventOS runs live events — 506 meetings, 200 exhibitors, 50 vendors on the floor at IMEX
            America. This page registers six of its operations as WebMCP tools on{" "}
            <code>document.modelContext</code>. An agent driving this browser discovers them the
            moment the page loads and calls them in the user&rsquo;s own session: no API key, no
            OAuth grant, no server the agent has to be told about.
          </p>

          <div className="hero-actions">
            <a className="btn primary" href={CHATGPT} target="_blank" rel="noreferrer">
              Try with ChatGPT
            </a>
            <a className="btn ghost" href="/console">
              Open the MCP console
            </a>
            <a className="btn ghost" href={REPO} target="_blank" rel="noreferrer">
              Source on GitHub
            </a>
          </div>
          <p className="hero-note">
            Open this URL in an agentic browser, then ask: <em>&ldquo;What tools does this page
            offer? Check vendor status for IMEX and tell me what&rsquo;s at risk.&rdquo;</em> Or run any
            tool yourself below — the buttons call through the registered surface, exactly as an
            agent would.
          </p>
          </div>

          <aside className="receipt" aria-label="Live registration state">
            <div className="receipt-head">
              <span className={`dot ${status ? "on" : "off"}`} />
              registration
            </div>
            <dl className="receipt-rows">
              <div>
                <dt>surface</dt>
                <dd className="mono">{status ? status.surfaces.join(", ") : "…"}</dd>
              </div>
              <div>
                <dt>host</dt>
                <dd className="mono">
                  {status ? (status.native ? "native WebMCP" : "shim (no host detected)") : "…"}
                </dd>
              </div>
              <div>
                <dt>tools</dt>
                <dd className="mono">{status ? status.registered.length : "…"}</dd>
              </div>
            </dl>
            <ul className="receipt-tools">
              {TOOLS.map((tool) => (
                <li key={tool.name}>
                  <span className={`tick${status?.registered.includes(tool.name) ? " on" : ""}`} />
                  {tool.name}
                </li>
              ))}
            </ul>
            <p className="receipt-foot">
              Verify in the console: <code>window.__eventosWebMCP</code>
            </p>
          </aside>
        </section>

        <section className="stats">
          <Stat value="6" label="tools registered" />
          <Stat value={String(liveCount)} label="backed by live agents" />
          <Stat value="0" label="credentials required" />
          <Stat value="document.modelContext" label="registration surface" mono />
        </section>

        <section>
          <h2 className="section-heading">What this page publishes</h2>
          <p className="section-sub">
            Every tool returns a <code>content</code> block for the model plus{" "}
            <code>structuredContent</code> for hosts that read it, and every payload carries a{" "}
            <code>source</code> field — so an agent can tell a number measured by the live fleet from
            one produced by the catalog model.
          </p>

          <div className="tool-grid">
            {TOOLS.map((tool) => (
              <ToolCard
                key={tool.name}
                tool={tool}
                expanded={open === tool.name}
                onToggle={() => setOpen(open === tool.name ? null : tool.name)}
                args={argsFor(tool)}
                onArg={(key, value) => setArg(tool.name, key, value)}
                onRun={() => run(tool)}
                state={runs[tool.name] ?? IDLE}
              />
            ))}
          </div>
        </section>

        <section>
          <h2 className="section-heading">How it fits together</h2>
          <div className="arch">
            <ArchStep
              step="1"
              title="The agent arrives"
              body="No configuration step. The browser hands the agent whatever this page registered on document.modelContext during load."
            />
            <ArchStep
              step="2"
              title="Tools run in the tab"
              body="execute() runs in the page, in the user's session. Three tools reach the live eventOS agent fleet over MCP through a same-origin proxy; three answer from the local catalog."
            />
            <ArchStep
              step="3"
              title="The fleet answers"
              body="A five-agent fleet on Cloud Run — Booking, Insight, Comms, Vendor, Compliance — exposes 12 MCP tools over JSON-RPC 2.0. The console shows that traffic on the wire."
            />
          </div>
          <p className="section-sub">
            The same fleet is reachable as a conventional MCP server, and{" "}
            <a href="/console">the console</a> drives it directly so you can read every JSON-RPC
            frame. WebMCP is the layer that removes the setup: the browser is already authenticated,
            so the page can just offer the tools.
          </p>
        </section>

        {status && (status.errors.length > 0 || !status.native) && (
          <section className="notice">
            <strong>Registration detail.</strong>{" "}
            {!status.native && (
              <>
                This browser exposes no WebMCP API, so eventOS installed a same-shape shim on{" "}
                <code>document.modelContext</code> and registered into it. The tools below are fully
                functional; a WebMCP-capable browser would pick up the identical registrations.{" "}
              </>
            )}
            {status.errors.length > 0 && <>Errors: {status.errors.join("; ")}</>}
          </section>
        )}
      </main>

      <footer className="footer">
        eventOS over WebMCP · six tools on <code>document.modelContext</code> ·{" "}
        <a href={REPO} target="_blank" rel="noreferrer">
          GitHub
        </a>{" "}
        ·{" "}
        <a href={`${REPO}/blob/main/LICENSE`} target="_blank" rel="noreferrer">
          MIT
        </a>{" "}
        · <a href="/console">MCP console</a>
      </footer>
    </>
  );
}

function Stat({ value, label, mono }: { value: string; label: string; mono?: boolean }) {
  return (
    <div className="stat">
      <div className={`stat-value${mono ? " mono" : ""}`}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function ArchStep({ step, title, body }: { step: string; title: string; body: string }) {
  return (
    <div className="arch-step">
      <div className="arch-num">{step}</div>
      <div>
        <div className="arch-title">{title}</div>
        <p className="arch-body">{body}</p>
      </div>
    </div>
  );
}

function ToolCard({
  tool,
  expanded,
  onToggle,
  args,
  onArg,
  onRun,
  state,
}: {
  tool: WebMcpToolDescriptor;
  expanded: boolean;
  onToggle: () => void;
  args: Record<string, string>;
  onArg: (key: string, value: string) => void;
  onRun: () => void;
  state: RunState;
}) {
  const card = TOOL_CARDS[tool.name];
  const fields = Object.entries(tool.inputSchema.properties ?? {});
  const required = tool.inputSchema.required ?? [];

  const text =
    state.result?.content?.map((block) => block.text).join("\n\n") ?? state.error ?? null;

  return (
    <article className={`tool-card${expanded ? " expanded" : ""}`}>
      <button className="tool-card-head" onClick={onToggle} aria-expanded={expanded}>
        <div>
          <div className="tool-card-name">{tool.name}</div>
          <div className="tool-card-headline">{card?.headline}</div>
        </div>
        <span className={`chip ${card?.backing === "live" ? "live" : ""}`}>
          {card?.backing === "live" ? "live fleet" : "catalog"}
        </span>
      </button>

      <p className="tool-card-desc">{tool.description}</p>

      <div className="schema-row">
        {fields.length === 0 ? (
          <span className="schema-none">no input</span>
        ) : (
          fields.map(([key, schema]) => (
            <span key={key} className="schema-chip">
              {key}
              <em>{schema.type}</em>
              {required.includes(key) && <b>required</b>}
            </span>
          ))
        )}
      </div>

      {expanded && (
        <div className="tool-runner">
          {fields.map(([key, schema]) => (
            <label key={key} className="runner-field">
              <span className="runner-label">
                {key}
                {required.includes(key) && <b> *</b>}
              </span>
              <input
                className="input"
                value={args[key] ?? ""}
                placeholder={schema.description}
                onChange={(event) => onArg(key, event.target.value)}
              />
            </label>
          ))}

          <div className="runner-actions">
            <button className="btn primary small" onClick={onRun} disabled={state.running}>
              {state.running ? "Calling…" : "Call tool"}
            </button>
            {state.ms !== null && <span className="hint">{state.ms} ms</span>}
            {state.result?.isError && <span className="hint err">isError: true</span>}
          </div>

          {text && <pre className={`json${state.error ? " err" : ""}`}>{text}</pre>}
        </div>
      )}
    </article>
  );
}
