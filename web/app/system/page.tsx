"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-64 flex-1">
        <TopBar />
        <main className="space-y-6 p-6">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <InfoCard icon={Settings} label={t("version")} value={data?.version || "-"} />
                <InfoCard icon={Database} label={t("database")} value={data?.database_path || "-"} />
                <InfoCard icon={Users} label={t("totalUsers")} value={data?.total_users ?? "-"} />
                <InfoCard icon={Key} label={t("totalCredentials")} value={data?.total_credentials ?? "-"} />
                <InfoCard icon={Server} label="Nodes" value={data?.total_nodes ?? "-"} />
                <InfoCard icon={Heart} label={t("health")} value="Healthy" color="text-success" />
              </div>
              <ResourceChart cpu={35} memory={48} disk={22} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: any;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="rounded-xl bg-primary/15 p-3">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={`text-lg font-semibold ${color || ""}`}>{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}
