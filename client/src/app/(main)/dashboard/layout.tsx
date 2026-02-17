import type { ReactNode } from "react";

import Link from "next/link";
import { LayoutDashboard, Settings } from "lucide-react";

import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { users } from "@/data/users";
import { cn } from "@/lib/utils";

import { AccountSwitcher } from "./_components/sidebar/account-switcher";
import { LayoutControls } from "./_components/sidebar/layout-controls";
import { ThemeSwitcher } from "./_components/sidebar/theme-switcher";
import Logo from "@/components/logo";

export default async function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col">
      <header
        className={cn(
          "flex h-14 shrink-0 items-center gap-2 border-b sticky top-0 z-50 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60",
        )}
      >
        <div className="flex w-full items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-4">
            <Link href="/dashboard/default" className="flex items-center gap-2">
              <Logo height={40} width={120} variant="isolated-monochrome-black" className="dark:invert" />
            </Link>
            <Separator orientation="vertical" className="h-6" />
            <nav className="flex items-center gap-1">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/default">
                  <LayoutDashboard className="size-4 mr-2" />
                  Dashboard
                </Link>
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/dashboard/crm">
                  <Settings className="size-4 mr-2" />
                  Provisioning
                </Link>
              </Button>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <LayoutControls />
            <ThemeSwitcher />
            <AccountSwitcher users={users} />
          </div>
        </div>
      </header>
      <main className="flex-1 p-4 md:p-6">{children}</main>
    </div>
  );
}
