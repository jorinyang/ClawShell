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
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <Shield className="h-7 w-7 text-primary" />
        <span className="text-lg font-bold text-foreground">ClawShell</span>
        <span className="ml-1 rounded bg-primary/20 px-1.5 py-0.5 text-xs font-medium text-primary">
          v2.0
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              {t(item.labelKey)}
            </Link>
          );
        })}
      </nav>

      {/* User Info */}
      <div className="border-t border-border p-4">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/20 text-sm font-bold text-primary">
            {user?.display_name?.[0]?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 overflow-hidden">
            <p className="truncate text-sm font-medium">{user?.display_name || "User"}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.role || ""}</p>
          </div>
        </div>
        <button
          onClick={() => {
            clearAuth();
            window.location.href = "/login";
          }}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut className="h-4 w-4" />
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}
