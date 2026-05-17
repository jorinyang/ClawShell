"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { StatusCard } from "@/components/StatusCard";
import { EngineStatus } from "@/components/EngineStatus";
import { ResourceChart } from "@/components/ResourceChart";
import { Users, Activity, Key, Server, Wifi, Monitor, FileText } from "lucide-react";

interface DashboardData {
  total_users: number;
  active_users: number;
  total_credentials: number;
  total_nodes: number;
  online_nodes: number;
  active_sessions: number;
  recent_audit_count: number;
}

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getDashboard()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-64 items-center justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6 max-w-[1200px]">
        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          <StatusCard
            title={t("totalUsers")}
            value={data?.total_users ?? 0}
            icon={Users}
          />
          <StatusCard
            title={t("activeUsers")}
            value={data?.active_users ?? 0}
            icon={Activity}
            color="success"
          />
          <StatusCard
            title={t("totalCredentials")}
            value={data?.total_credentials ?? 0}
            icon={Key}
          />
          <StatusCard
            title={t("totalNodes")}
            value={data?.total_nodes ?? 0}
            icon={Server}
          />
        </div>

        {/* Second Row */}
        <div className="grid grid-cols-3 gap-4">
          <StatusCard
            title={t("onlineNodes")}
            value={data?.online_nodes ?? 0}
            icon={Wifi}
            color="success"
          />
          <StatusCard
            title={t("activeSessions")}
            value={data?.active_sessions ?? 0}
            icon={Monitor}
            color="info"
          />
          <StatusCard
            title={t("recentAudit")}
            value={data?.recent_audit_count ?? 0}
            icon={FileText}
          />
        </div>

        {/* Engine & Resources */}
        <div className="grid grid-cols-2 gap-4">
          <EngineStatus
            onlineNodes={data?.online_nodes ?? 0}
            totalNodes={data?.total_nodes ?? 0}
            activeSessions={data?.active_sessions ?? 0}
            t={t}
          />
          <ResourceChart cpu={45} memory={62} disk={38} t={t} />
        </div>
      </div>
    </AppShell>
  );
}
