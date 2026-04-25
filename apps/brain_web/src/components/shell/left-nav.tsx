"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";

interface NavItem {
  href: string;
  label: string;
  /** Alternative URL prefix to match against when highlighting the active
   *  row. Used when a nav entry deep-links into a specific sub-tab (e.g.
   *  Settings → `/settings/general`) but any `/settings/*` pathname
   *  should still light up "Settings". */
  matchPrefix?: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/chat", label: "Chat" },
  { href: "/inbox", label: "Inbox" },
  { href: "/browse", label: "Browse" },
  { href: "/pending", label: "Pending" },
  { href: "/bulk", label: "Bulk" },
  { href: "/settings/general", label: "Settings", matchPrefix: "/settings" },
  { href: "/setup", label: "Setup" },
];

export function LeftNav() {
  const pathname = usePathname();

  function handleNewChat() {
    // Task 13 wires this to the real thread-create action. For now, a no-op
    // with a console breadcrumb is enough for the shell skeleton.
    // eslint-disable-next-line no-console
    console.log("[shell] New chat clicked (Task 13 wires this)");
  }

  return (
    // Class ``nav`` matches the brand-skin.css selectors so the active-item
    // ember inset accent (``.nav-item.active`` → ``box-shadow: inset 2px 0 0
    // var(--brand-ember)``) cascades automatically. Wrapped in ``leftnav``
    // too for any legacy Tailwind selectors that may still target the old
    // class name.
    <nav
      aria-label="Primary"
      className="nav leftnav flex flex-col gap-2 p-3"
    >
      <Button
        type="button"
        onClick={handleNewChat}
        aria-label="New chat"
        className="new-chat-btn nav-new w-full justify-start"
        size="sm"
      >
        + New chat
      </Button>

      <ul className="mt-2 flex flex-col gap-1" role="list">
        {NAV_ITEMS.map((item) => {
          const matchBase = item.matchPrefix ?? item.href;
          const active =
            pathname === matchBase ||
            pathname?.startsWith(`${matchBase}/`) ||
            pathname === item.href;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={[
                  "nav-item flex items-center px-3 py-1.5 text-sm",
                  active ? "active" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
