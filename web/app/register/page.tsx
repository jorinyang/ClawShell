"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Shield } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [accountId, setAccountId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const t = (key: string) => {
    const zh: Record<string, string> = {
      title: "Register — ClawShell",
      subtitle: "Create your account to get started",
      accountId: "Account ID",
      accountPlaceholder: "Enter account ID",
      displayName: "Display Name",
      displayPlaceholder: "Enter your name",
      password: "Password",
      passwordPlaceholder: "Enter password",
      passwordConfirm: "Confirm Password",
      confirmPlaceholder: "Re-enter password",
      registerButton: "Register",
      registering: "Registering...",
      successTitle: "Registration Submitted!",
      successMsg: "Your account has been created and is pending admin approval. You will be notified once approved.",
      backToLogin: "Back to Login",
      passwordMismatch: "Passwords do not match",
      registerFailed: "Registration failed. Please try again.",
      hasAccount: "Already have an account?",
      loginLink: "Sign in",
    };
    return zh[key] || key;
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== passwordConfirm) {
      setError(t("passwordMismatch"));
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    try {
      await api.register(accountId, displayName, password);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || t("registerFailed"));
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div className="w-full max-w-[360px] text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(34,197,94,0.12)]">
            <Shield className="h-5 w-5 text-green-400" />
          </div>
          <h1 className="text-lg font-medium text-foreground">{t("successTitle")}</h1>
          <p className="mt-2 text-sm text-text-tertiary">{t("successMsg")}</p>
          <Button className="mt-6 w-full" variant="outline" onClick={() => router.push("/login")}>
            {t("backToLogin")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-[360px]">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[rgba(94,106,210,0.12)]">
            <Shield className="h-5 w-5 text-accent" />
          </div>
          <h1 className="text-lg font-medium text-foreground">{t("title")}</h1>
          <p className="mt-1 text-xs text-text-quaternary">{t("subtitle")}</p>
        </div>

        <form onSubmit={handleRegister} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="accountId">{t("accountId")}</Label>
            <Input
              id="accountId"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              placeholder={t("accountPlaceholder")}
              required
              autoFocus
              minLength={2}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="displayName">{t("displayName")}</Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("displayPlaceholder")}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">{t("password")}</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("passwordPlaceholder")}
              required
              minLength={6}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="passwordConfirm">{t("passwordConfirm")}</Label>
            <Input
              id="passwordConfirm"
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              placeholder={t("confirmPlaceholder")}
              required
              minLength={6}
            />
          </div>
          {error && (
            <div className="rounded-[6px] bg-[rgba(239,68,68,0.08)] px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
          <Button type="submit" variant="default" className="w-full" disabled={loading}>
            {loading ? t("registering") : t("registerButton")}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-text-quaternary">
          {t("hasAccount")}{" "}
          <Link href="/login" className="text-accent hover:underline">
            {t("loginLink")}
          </Link>
        </p>
      </div>
    </div>
  );
}
