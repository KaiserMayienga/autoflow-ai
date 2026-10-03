import "./globals.css";
import type { Metadata, Viewport } from "next";

export const metadata: Metadata = { title: "AutoFlow AI", description: "AI workflow automation for automotive repair and upgrade workshops" };
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body>{children}</body></html>);
}
