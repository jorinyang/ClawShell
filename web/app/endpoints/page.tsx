"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Pencil, X } from "lucide-react";

export default function EndpointsPage() {
  const t = useTranslations("endpoints");
  const tc = useTranslations("common");
  const [endpoints, setEndpoints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<any>(null);
  const [formData, setFormData] = useState({ address: "", port: "", protocol: "tcp" });

  const load = () => {
    setLoading(true);
    api
      .getEndpoints()
      .then(setEndpoints)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    try {
      await api.updateEndpoint(editing.id, formData);
      setEditing(null);
      load();
    } catch {}
  };

  const columns = [
    { key: "name", header: t("name"), className: "text-text-secondary" },
    {
      key: "type",
      header: t("type"),
      render: (ep: any) => <Badge variant="outline">{ep.type}</Badge>,
    },
    { key: "address", header: t("address"), className: "text-text-tertiary font-mono text-xs" },
    { key: "port", header: t("port"), className: "text-text-tertiary" },
    { key: "protocol", header: t("protocol"), className: "text-text-tertiary" },
    {
      key: "actions",
      header: tc("actions"),
      className: "w-[60px]",
      render: (ep: any) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setEditing(ep);
            setFormData({ address: ep.address || "", port: String(ep.port || ""), protocol: ep.protocol || "tcp" });
          }}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      ),
    },
  ];

  return (
    <AppShell>
      <div className="space-y-4 max-w-[1200px]">
        {/* Edit Form */}
        {editing && (
          <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-text-secondary">
                {t("update")}: {editing.name}
              </span>
              <Button variant="ghost" size="icon" onClick={() => setEditing(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <form onSubmit={handleUpdate} className="grid grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <Label>{t("address")}</Label>
                <Input value={formData.address} onChange={(e) => setFormData({ ...formData, address: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>{t("port")}</Label>
                <Input value={formData.port} onChange={(e) => setFormData({ ...formData, port: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>{t("protocol")}</Label>
                <Input value={formData.protocol} onChange={(e) => setFormData({ ...formData, protocol: e.target.value })} />
              </div>
              <div>
                <Button type="submit" variant="default">{tc("save")}</Button>
              </div>
            </form>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : (
          <DataTable columns={columns} data={endpoints} emptyMessage={tc("noData")} />
        )}
      </div>
    </AppShell>
  );
}
