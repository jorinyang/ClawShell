"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
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
    {
      key: "node_id",
      header: t("nodeId"),
      render: (n: any) => <span className="font-mono text-xs text-text-tertiary">{n.node_id?.slice(0, 12)}…</span>,
    },
    { key: "hostname", header: t("hostname"), className: "text-text-secondary" },
    { key: "ip_address", header: t("ip"), className: "text-text-tertiary" },
    { key: "os", header: t("os"), className: "text-text-tertiary" },
    { key: "version", header: t("version"), className: "text-text-tertiary" },
    {
      key: "status",
      header: t("status"),
      render: (n: any) => (
        <span className="inline-flex items-center gap-1.5 text-xs">
          <span className={`h-1.5 w-1.5 rounded-full ${n.enabled !== false ? "bg-success" : "bg-text-quaternary"}`} />
          <span className={n.enabled !== false ? "text-success" : "text-text-quaternary"}>
            {n.enabled !== false ? tc("enabled") : tc("disabled")}
          </span>
        </span>
      ),
    },
    {
      key: "last_seen",
      header: t("lastSeen"),
      render: (n: any) => <span className="text-xs text-text-quaternary">{formatDate(n.last_seen)}</span>,
    },
    {
      key: "actions",
      header: tc("actions"),
      className: "w-[80px]",
      render: (n: any) => (
        <div className="flex gap-0.5">
          <Button variant="ghost" size="icon" onClick={() => toggleNode(n.node_id, n.enabled !== false)} title={n.enabled !== false ? t("disable") : t("enable")}>
            <Power className={`h-3.5 w-3.5 ${n.enabled !== false ? "text-success" : "text-text-quaternary"}`} />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => removeNode(n.node_id)} title={t("remove")}>
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <AppShell>
      <div className="space-y-4 max-w-[1200px]">
        <div className="flex items-center justify-between">
          <p className="text-xs text-text-quaternary">{tc("total")}: {nodes.length} {tc("items")}</p>
          <Button variant="secondary" size="sm" onClick={load}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> 刷新
          </Button>
        </div>
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : (
          <DataTable columns={columns} data={nodes} emptyMessage={tc("noData")} />
        )}
      </div>
    </AppShell>
  );
}
