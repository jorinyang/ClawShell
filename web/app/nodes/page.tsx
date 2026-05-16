"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { Power, Trash2, RefreshCw } from "lucide-react";

export default function NodesPage() {
  const t = useTranslations("nodes");
  const tc = useTranslations("common");
  const [nodes, setNodes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api
      .getNodes()
      .then(setNodes)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const toggleNode = async (id: string, enabled: boolean) => {
    try {
      await api.updateNode(id, { enabled: !enabled });
      load();
    } catch {}
  };

  const removeNode = async (id: string) => {
    if (!confirm(t("confirmRemove"))) return;
    try {
      await api.deleteNode(id);
      load();
    } catch {}
  };

  const columns = [
    { key: "node_id", header: t("nodeId"), render: (n: any) => <span className="font-mono text-xs">{n.node_id?.slice(0, 12)}…</span> },
    { key: "hostname", header: t("hostname") },
    { key: "ip_address", header: t("ip") },
    { key: "os", header: t("os") },
    { key: "version", header: t("version") },
    {
      key: "status",
      header: t("status"),
      render: (n: any) => (
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${n.enabled !== false ? "text-success" : "text-muted-foreground"}`}>
          <span className={`h-2 w-2 rounded-full ${n.enabled !== false ? "bg-success" : "bg-muted-foreground"}`} />
          {n.enabled !== false ? tc("enabled") : tc("disabled")}
        </span>
      ),
    },
    {
      key: "last_seen",
      header: t("lastSeen"),
      render: (n: any) => <span className="text-xs text-muted-foreground">{formatDate(n.last_seen)}</span>,
    },
    {
      key: "actions",
      header: tc("actions"),
      render: (n: any) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={() => toggleNode(n.node_id, n.enabled !== false)} title={n.enabled !== false ? t("disable") : t("enable")}>
            <Power className={`h-4 w-4 ${n.enabled !== false ? "text-success" : "text-muted-foreground"}`} />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => removeNode(n.node_id)} title={t("remove")}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-64 flex-1">
        <TopBar />
        <main className="p-6">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{tc("total")}: {nodes.length} {tc("items")}</p>
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw className="mr-2 h-4 w-4" /> 刷新
            </Button>
          </div>
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <DataTable columns={columns} data={nodes} emptyMessage={tc("noData")} />
          )}
        </main>
      </div>
    </div>
  );
}
