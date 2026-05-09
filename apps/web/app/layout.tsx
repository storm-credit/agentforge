import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Forge",
  description: "Governed internal agent build platform",
};

const navItems = [
  { href: "/", label: "Overview" },
  { href: "/agents", label: "Agents" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/eval", label: "Eval" },
  { href: "/audit", label: "Audit" },
  { href: "/admin/settings", label: "Settings" },
];

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
          <nav aria-label="Primary">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}

