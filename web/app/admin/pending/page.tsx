"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock, CheckCircle, XCircle, UserCheck } from "lucide-react";

interface PendingUser {
  user_id: string;
  account_id: string;
  display_name: string;
  pinyin_prefix: string;
  status: string;
  role: string;
  created_at: string;
}

export default function PendingUsersPage() {
  const [users, setUsers] = useState<PendingUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState<string | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await api.getPendingUsers();
      setUsers(data.users || []);
    } catch (e) {
      console.error("Failed to load pending users", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleApprove = async (userId: string) => {
    setApproving(userId);
    try {
      const result = await api.approveUser(userId);
      // Refresh list
      await loadUsers();
    } catch (e: any) {
      alert(e.message || "Approval failed");
    } finally {
      setApproving(null);
    }
  };

  const handleDisable = async (userId: string) => {
    if (!confirm("Disable this user?")) return;
    try {
      await api.disableUser(userId);
      await loadUsers();
    } catch (e: any) {
      alert(e.message || "Failed to disable user");
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-lg font-medium text-foreground">Pending Approvals</h1>
        <p className="mt-1 text-xs text-text-quaternary">
          Users awaiting admin approval before account activation
        </p>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-sm text-text-quaternary">
          Loading...
        </div>
      ) : users.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <CheckCircle className="mb-3 h-8 w-8 text-green-400" />
            <p className="text-sm text-text-tertiary">No pending approvals</p>
            <p className="mt-1 text-xs text-text-quaternary">All users have been processed</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {users.map((user) => (
            <Card key={user.user_id}>
              <CardContent className="flex items-center justify-between py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[rgba(249,115,22,0.12)] text-xs font-medium text-orange-400">
                    {user.display_name?.[0]?.toUpperCase() || "?"}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{user.display_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-text-quaternary">@{user.account_id}</span>
                      {user.pinyin_prefix && (
                        <Badge variant="secondary" className="text-[10px]">
                          prefix: {user.pinyin_prefix}
                        </Badge>
                      )}
                      <Badge variant="outline" className="text-[10px] text-orange-400 border-orange-400/30">
                        <Clock className="mr-1 h-2.5 w-2.5" />
                        Pending
                      </Badge>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => handleApprove(user.user_id)}
                    disabled={approving === user.user_id}
                  >
                    {approving === user.user_id ? (
                      <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                    ) : (
                      <>
                        <UserCheck className="mr-1.5 h-3.5 w-3.5" />
                        Approve
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDisable(user.user_id)}
                  >
                    <XCircle className="mr-1.5 h-3.5 w-3.5" />
                    Reject
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
