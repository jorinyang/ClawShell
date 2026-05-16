"use client";

import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { useAuthStore } from "@/lib/auth-store";
import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/": "dashboard",
  "/system": "system",
  "/nodes": "nodes",
  "/users": "users",
  "/credentials": "credentials",
  "/endpoints": "endpoints",
  "/audit": "audit",
};

export function TopBar() {
  const t = useTranslations("common");
  const pathname = usePathname();
  const titleKey = pageTitles[pathname] || "dashboard";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-card/80 px-6 backdrop-blur">
      <h1 className="text-xl font-semibold">{t(titleKey)}</h1>
      <div className="flex items-center gap-4">
        <LanguageSwitcher />
      </div>
    </header>
  );
}
