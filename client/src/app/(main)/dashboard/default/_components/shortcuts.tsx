"use client";

import {
  Activity,
  CirclePlus,
  History,
  Network,
  PackagePlus,
  Router,
  UserPlus,
} from "lucide-react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type ScrollTarget = { id: string; tabEvent?: string };

type ShortcutItem = {
  label: string;
  icon: LucideIcon;
  color: string;
  href?: string;
  scrollTo?: ScrollTarget;
};

const shortcuts: ShortcutItem[] = [
  {
    label: "Add customer",
    icon: UserPlus,
    href: "/dashboard/crm?tab=customers",
    color: "text-green-600",
  },
  {
    label: "Add plan",
    icon: PackagePlus,
    href: "/dashboard/crm?tab=plans",
    color: "text-purple-600",
  },
  {
    label: "Add service",
    icon: CirclePlus,
    href: "/dashboard/crm?tab=services",
    color: "text-blue-600",
  },
  {
    label: "Add router",
    icon: Router,
    scrollTo: { id: "routers-section" },
    color: "text-orange-600",
  },
  {
    label: "View topology",
    icon: Network,
    href: "/dashboard/topology",
    color: "text-cyan-600",
  },
  {
    label: "View active sessions",
    icon: Activity,
    scrollTo: { id: "sessions-tabs", tabEvent: "active" },
    color: "text-emerald-600",
  },
  {
    label: "View session history",
    icon: History,
    scrollTo: { id: "sessions-tabs", tabEvent: "history" },
    color: "text-indigo-600",
  },
];

function handleScrollTo(target: ScrollTarget) {
  if (target.tabEvent) {
    window.dispatchEvent(
      new CustomEvent("switch-sessions-tab", { detail: target.tabEvent })
    );
  }
  const el = document.getElementById(target.id);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

export function Shortcuts() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Shortcuts</CardTitle>
        <CardAction>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {shortcuts.map((shortcut) => {
            const Icon = shortcut.icon;
            const className = "inline-flex items-center gap-1.5 text-sm hover:underline";

            if (shortcut.href) {
              return (
                <Link key={shortcut.label} href={shortcut.href} className={className}>
                  <Icon className={`size-4 ${shortcut.color}`} />
                  {shortcut.label}
                </Link>
              );
            }

            return (
              <button
                key={shortcut.label}
                type="button"
                className={`${className} cursor-pointer`}
                onClick={() => shortcut.scrollTo && handleScrollTo(shortcut.scrollTo)}
              >
                <Icon className={`size-4 ${shortcut.color}`} />
                {shortcut.label}
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
