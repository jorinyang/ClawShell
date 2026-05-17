"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { ResourceChart } from "@/components/ResourceChart";
import { Settings, Database, Users, Key, Server, Clock, Heart } from "lucide-react";

export default function SystemPage() {
  const t = useTranslations("system");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getSystem()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppShell>
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : (
        <div className="space-y-6 max-w-[1200px]">
          {/* System Info Grid */}
          <div className="grid grid-cols-3 gap-4">
            <InfoCard icon={Settings} label={t("version")} value={data?.version || "-"} />
            <InfoCard icon={Database} label={t("database")} value={data?.database_path || "-"} />
            <InfoCard icon={Users} label={t("totalUsers")} value={data?.total_users ?? "-"} />
            <InfoCard icon={Key} label={t("totalCredentials")} value={data?.total_credentials ?? "-"} />
            <InfoCard icon={Server} label="Nodes" value={data?.total_nodes ?? "-"} />
            <InfoCard icon={Clock} label={t("uptime")} value={data?.uptime ?? "-"} />
          </div>

          {/* Health + Resources */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
              <div className="flex items-center gap-2 mb-4">
                <Heart className="h-4 w-4 text-text-tertiary" />
                <span className="text-sm font-medium text-text-secondary">{t("health")}</span>
              </div>
              <div className="flex items-center gap-2.5">
                <span className="h-2 w-2 rounded-full bg-success" />
                <span className="text-sm font-medium text-success">Healthy</span>
              </div>
            </div>
            <ResourceChart cpu={35} memory={48} disk={22} />
          </div>
        </div>
      )}
    </AppShell>
  );
}

function InfoCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
      <div className="flex items-center gap-3">
        <Icon className="h-4 w-4 text-text-quaternary" />
        <div className="min-w-0">
          <p className="text-xs text-text-quaternary">{label}</p>
          <p className="text-sm font-medium text-foreground truncate mt-0.5">{value}</p>
        </div>
      </div>
    </div>
  );
}
