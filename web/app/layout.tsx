import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "eventOS — MCP Agent Fleet",
  description:
    "A browser MCP client driving a five-agent event operations fleet over Model Context Protocol.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
