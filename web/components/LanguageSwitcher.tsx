"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { Globe } from "lucide-react";

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();

  const toggle = () => {
    const next = locale === "zh" ? "en" : "zh";
    document.cookie = `locale=${next};path=/;max-age=31536000`;
    router.refresh();
  };

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
    >
      <Globe className="h-4 w-4" />
      {locale === "zh" ? "中文" : "EN"}
    </button>
  );
}
