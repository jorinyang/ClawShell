"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/auth-store";
import {
  LayoutDashboard,
  Server,
  Users,
  Key,
  Globe,
  FileText,
  Settings,
  LogOut,
  Shield,
} from "lucide-react";

const navItems = [
  { href: "/", icon: LayoutDashboard, labelKey: "dashboard" },
  { href: "/system", icon: Settings, labelKey: "system" },
  { href: "/nodes", icon: Server, labelKey: "nodes" },
  { href: "/users", icon: Users, labelKey: "users" },
  { href: "/credentials", icon: Key, labelKey: "credentials" },
  { href: "/endpoints", icon: Globe, labelKey: "endpoints" },
  { href: "/audit", icon: FileText, labelKey: "audit" },
];

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("common");
  const { user, clearAuth } = useAuthStore();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-panel">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-5">
        <Shield className="h-5 w-5 text-accent" />
        <span className="text-[15px] font-medium text-foreground">ClawShell</span>
        <span className="rounded-[4px] bg-[rgba(94,106,210,0.15)] px-1.5 py-0.5 text-[10px] font-medium text-accent">
          v2
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex h-9 items-center gap-2.5 rounded-[6px] px-3 text-sm transition-colors",
                isActive
                  ? "bg-[rgba(94,106,210,0.12)] text-accent"
                  : "text-text-tertiary hover:bg-[rgba(255,255,255,0.04)] hover:text-text-secondary"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-border p-3">
        <div className="mb-2 flex items-center gap-2.5 px-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[rgba(94,106,210,0.15)] text-xs font-medium text-accent">
            {user?.display_name?.[0]?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="truncate text-sm font-medium text-text-secondary">{user?.display_name || "User"}</p>
            <p className="truncate text-[11px] text-text-quaternary">{user?.role || ""}</p>
          </div>
        </div>
        <button
          onClick={() => {
            clearAuth();
            window.location.href = "/login";
          }}
          className="flex h-8 w-full items-center gap-2 rounded-[6px] px-3 text-xs text-text-quaternary transition-colors hover:bg-[rgba(239,68,68,0.08)] hover:text-destructive"
        >
          <LogOut className="h-3.5 w-3.5" />
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}
