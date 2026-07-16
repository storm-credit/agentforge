import type { Metadata } from "next";
import Link from "next/link";
import localFont from "next/font/local";
import "./globals.css";
import { NavLinks } from "./components/NavLinks";
import { RoleSwitcher } from "./components/RoleSwitcher";
import { ThemeSwitcher } from "./components/ThemeSwitcher";

// Pretendard (SIL OFL 1.1), self-hosted variable font — clean Korean/Latin
// enterprise face. Exposed as --font-pretendard; globals.css --font-sans
// falls back to the system stack if it ever fails to load.
const pretendard = localFont({
  src: "./fonts/PretendardVariable.woff2",
  display: "swap",
  weight: "45 920",
  variable: "--font-pretendard",
});

export const metadata: Metadata = {
  title: "Agent Forge",
  description: "Governed internal agent build platform",
};

const navItems = [
  { href: "/", label: "Overview" },
  { href: "/agents", label: "Agents" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/chat", label: "Chat" },
  { href: "/runs", label: "Runs" },
  { href: "/eval", label: "Eval" },
  { href: "/audit", label: "Audit" },
  { href: "/admin/settings", label: "Settings" },
];

// Pre-applies the persisted theme before first paint to avoid a flash of the
// wrong theme. Runs inline, so it must stay tiny and defensive.
const themeInitScript =
  'try{var t=localStorage.getItem("af-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}catch(e){}';

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={pretendard.variable} suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <aside className="sidebar">
          <Link className="brand" href="/">
            <span className="brandMark">AF</span>
            <span>Agent Forge</span>
          </Link>
          <nav aria-label="Primary">
            <NavLinks items={navItems} />
          </nav>
          <div className="sidebarFooter">
            <RoleSwitcher />
            <ThemeSwitcher />
          </div>
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}
