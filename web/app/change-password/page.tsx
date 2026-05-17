"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound } from "lucide-react";

export default function ChangePasswordPage() {
  const t = useTranslations("changePassword");
  const router = useRouter();
  const { clearAuth } = useAuthStore();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError(t("mismatch"));
      return;
    }

    setLoading(true);
    try {
      await api.changePassword(oldPassword, newPassword);
      clearAuth();
      router.replace("/login");
    } catch (err: any) {
      setError(err.message || t("error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(245,158,11,0.12)]">
            <KeyRound className="h-5 w-5 text-warning" />
          </div>
          <h1 className="text-lg font-medium text-foreground">{t("title")}</h1>
          <p className="mt-1 text-xs text-text-quaternary">{t("subtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label>{t("oldPassword")}</Label>
            <Input
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("newPassword")}</Label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t("confirmPassword")}</Label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {error && (
            <div className="rounded-[6px] bg-[rgba(239,68,68,0.08)] px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" variant="default" className="w-full" disabled={loading}>
            {loading ? "..." : t("submit")}
          </Button>
        </form>
      </div>
    </div>
  );
}
