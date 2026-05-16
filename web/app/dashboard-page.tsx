"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
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
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="ml-64 flex-1">
          <TopBar />
          <div className="flex h-64 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-64 flex-1">
        <TopBar />
        <main className="space-y-6 p-6">
          {/* Stats Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatusCard
              title={t("totalUsers")}
              value={data?.total_users ?? 0}
              icon={Users}
              color="default"
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
              color="info"
            />
            <StatusCard
              title={t("totalNodes")}
              value={data?.total_nodes ?? 0}
              icon={Server}
              color="warning"
            />
          </div>

          {/* Second Row */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
              color="default"
            />
          </div>

          {/* Engine & Resources */}
          <div className="grid gap-6 lg:grid-cols-2">
            <EngineStatus
              onlineNodes={data?.online_nodes ?? 0}
              totalNodes={data?.total_nodes ?? 0}
              activeSessions={data?.active_sessions ?? 0}
            />
            <ResourceChart cpu={45} memory={62} disk={38} />
          </div>
        </main>
      </div>
    </div>
  );
}
