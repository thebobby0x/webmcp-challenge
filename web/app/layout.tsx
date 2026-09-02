import type { Metadata, Viewport } from "next";
import "./globals.css";
import WebMcpProvider from "./webmcp-provider";

const TITLE = "eventOS over WebMCP — six event-operations tools on document.modelContext";
const DESCRIPTION =
  "A live event operations platform that publishes six of its operations as WebMCP tools on document.modelContext: event sentiment, event list, P&L, vendor status, venue lookup and planner search. Three are backed by a live five-agent MCP fleet. No API key, no OAuth, no server setup — an agent driving the browser discovers and calls them in the user's own session.";

export const metadata: Metadata = {
  metadataBase: new URL("https://web-ebon-one-23.vercel.app"),
  title: TITLE,
  description: DESCRIPTION,
  applicationName: "eventOS over WebMCP",
  authors: [{ name: "studio0x" }],
  keywords: [
    "WebMCP",
    "document.modelContext",
    "Model Context Protocol",
    "MCP",
    "agentic browser",
    "event operations",
    "eventOS",
    "WebMCP Challenge",
  ],
  openGraph: {
    type: "website",
    title: TITLE,
    description: DESCRIPTION,
    siteName: "eventOS over WebMCP",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};

export const viewport: Viewport = {
  themeColor: "#0F0C0E",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Registers the six eventOS tools on document.modelContext for any
            agent driving this browser. Mounted here so every route offers them. */}
        <WebMcpProvider />
        {children}
      </body>
    </html>
  );
}
