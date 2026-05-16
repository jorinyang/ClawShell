"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    { key: "name", header: t("name") },
    { key: "type", header: t("type"), render: (ep: any) => <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{ep.type}</span> },
    { key: "address", header: t("address") },
    { key: "port", header: t("port") },
    { key: "protocol", header: t("protocol") },
    {
      key: "actions",
      header: tc("actions"),
      render: (ep: any) => (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setEditing(ep);
            setFormData({ address: ep.address || "", port: String(ep.port || ""), protocol: ep.protocol || "tcp" });
          }}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-64 flex-1">
        <TopBar />
        <main className="p-6">
          {editing && (
            <Card className="mb-6">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>{t("update")}: {editing.name}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => setEditing(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleUpdate} className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label>{t("address")}</Label>
                    <Input value={formData.address} onChange={(e) => setFormData({ ...formData, address: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("port")}</Label>
                    <Input value={formData.port} onChange={(e) => setFormData({ ...formData, port: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("protocol")}</Label>
                    <Input value={formData.protocol} onChange={(e) => setFormData({ ...formData, protocol: e.target.value })} />
                  </div>
                  <div>
                    <Button type="submit">{tc("save")}</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <DataTable columns={columns} data={endpoints} emptyMessage={tc("noData")} />
          )}
        </main>
      </div>
    </div>
  );
}
