"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = () => {
    setPage(0);
    load(0, search);
  };

  const columns = [
    {
      key: "timestamp",
      header: t("timestamp"),
      className: "w-[160px]",
      render: (l: any) => <span className="text-xs text-text-quaternary">{formatDate(l.timestamp)}</span>,
    },
    {
      key: "user_id",
      header: t("userId"),
      render: (l: any) => <span className="font-mono text-xs text-text-tertiary">{l.user_id?.slice(0, 8)}…</span>,
    },
    {
      key: "action",
      header: t("action"),
      render: (l: any) => <Badge variant="default">{l.action}</Badge>,
    },
    { key: "resource", header: t("resource"), className: "text-text-secondary" },
    {
      key: "detail",
      header: t("detail"),
      className: "max-w-[200px]",
      render: (l: any) => <span className="truncate block text-xs text-text-quaternary">{l.detail || "-"}</span>,
    },
    { key: "ip_address", header: t("ip"), className: "text-text-tertiary font-mono text-xs" },
  ];

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="space-y-4 max-w-[1200px]">
        {/* Search bar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-quaternary" />
            <Input
              className="pl-9"
              placeholder={`${tc("search")}...`}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={handleSearch}>
            <Search className="mr-1.5 h-3.5 w-3.5" /> {tc("filter")}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => { setSearch(""); setPage(0); load(0, ""); }}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> 刷新
          </Button>
          <span className="ml-auto text-xs text-text-quaternary">
            {tc("total")}: {total} {tc("items")}
          </span>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : (
          <>
            <DataTable columns={columns} data={logs} emptyMessage={tc("noData")} />
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <span className="text-xs text-text-quaternary">
                  Page {page + 1} / {totalPages}
                </span>
                <Button
                  variant="secondary"
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
      </div>
    </AppShell>
  );
}
