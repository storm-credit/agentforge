"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

// Sidebar navigation with an active-route highlight. Rendered inside the
// layout's <nav aria-label="Primary"> so the links stay direct children of
// the nav landmark (same accessible structure as before).
export function NavLinks({ items }: { items: ReadonlyArray<{ href: string; label: string }> }) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <>
      {items.map((item) => {
        const active = isActive(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
