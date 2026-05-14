import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { PrimaryNav } from "./nav";

export const metadata: Metadata = {
  title: "Agent Forge",
  description: "Governed internal agent build platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <aside className="sidebar">
          <Link className="brand" href="/">
            <span className="brandMark">AF</span>
            <span>Agent Forge</span>
          </Link>
          <PrimaryNav />
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}

