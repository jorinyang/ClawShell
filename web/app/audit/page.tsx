"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/utils";
import { Search, RefreshCw } from "lucide-react";

export default function AuditPage() {
  const t = useTranslations("audit");
  const tc = useTranslations("common");
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const load = (pageNum = 0, q = "") => {
    setLoading(true);
    const params: Record<string, string> = {
      offset: String(pageNum * pageSize),
      limit: String(pageSize),
    };
    if (q) params.search = q;
    api
      .getAuditLogs(params)
      .then((res) => {
        setLogs(res.logs || []);
        setTotal(res.total || 0);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(page, search);
  }, [page]);

  const handleSearch = () => {
    setPage(0);
    load(0, search);
  };

  const columns = [
    {
      key: "timestamp",
      header: t("timestamp"),
      render: (l: any) => <span className="text-xs text-muted-foreground">{formatDate(l.timestamp)}</span>,
    },
    { key: "user_id", header: t("userId"), render: (l: any) => <span className="font-mono text-xs">{l.user_id?.slice(0, 8)}…</span> },
    {
      key: "action",
      header: t("action"),
      render: (l: any) => <span className="rounded bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">{l.action}</span>,
    },
    { key: "resource", header: t("resource") },
    { key: "detail", header: t("detail"), render: (l: any) => <span className="max-w-xs truncate text-xs text-muted-foreground">{l.detail || "-"}</span> },
    { key: "ip_address", header: t("ip") },
  ];

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-64 flex-1">
        <TopBar />
        <main className="p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder={`${tc("search")}...`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>
            <Button variant="outline" size="sm" onClick={handleSearch}>
              <Search className="mr-2 h-4 w-4" /> {tc("filter")}
            </Button>
            <Button variant="outline" size="sm" onClick={() => { setSearch(""); setPage(0); load(0, ""); }}>
              <RefreshCw className="mr-2 h-4 w-4" /> 刷新
            </Button>
            <span className="ml-auto text-sm text-muted-foreground">
              {tc("total")}: {total} {tc("items")}
            </span>
          </div>

          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <>
              <DataTable columns={columns} data={logs} emptyMessage={tc("noData")} />
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Page {page + 1} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
