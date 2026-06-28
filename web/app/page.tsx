"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/lib/auth-store";
import { Shield, Terminal, Cpu, Layers, ExternalLink } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const { token, user } = useAuthStore();

  useEffect(() => {
    if (token) {
      if (user?.must_change_pwd) {
        router.replace("/change-password");
      } else {
        router.replace("/dashboard");
      }
    }
  }, [token, user, router]);

  if (token) return null;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* ── Nav ─────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.04)]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgba(94,106,210,0.15)]">
            <Shield className="h-4 w-4 text-accent" />
          </div>
          <span className="text-sm font-medium text-foreground">ClawShell</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(94,106,210,0.1)] text-accent">v3.0</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/register"
            className="text-xs text-text-secondary hover:text-foreground transition-colors"
          >
            Register
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 rounded-[6px] bg-accent px-3.5 py-1.5 text-xs font-medium text-white hover:bg-[rgba(94,106,210,0.8)] transition-colors"
          >
            Sign In
          </Link>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-16">
        <div className="w-full max-w-[640px] text-center">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-[rgba(94,106,210,0.12)]">
            <Shield className="h-7 w-7 text-accent" />
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-2">
            ClawShell v3.0
          </h1>
          <p className="text-sm text-text-tertiary mb-8 max-w-md mx-auto leading-relaxed">
            Pluggable exoskeleton enhancement layer for AI agent frameworks.
            Self-perception, self-adaptation, self-organization, multi-agent cluster — one command to install.
          </p>

          {/* ── Install Commands ───────────────────────── */}
          <div className="mb-2 text-left">
            <p className="text-xs font-medium text-text-secondary mb-2">One-command install</p>
            <div className="space-y-2">
              {/* Linux / macOS */}
              <div className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] p-3.5">
                <p className="text-[10px] font-medium text-text-quaternary mb-2 uppercase tracking-wider">Linux / macOS / WSL</p>
                <code className="block text-xs text-foreground font-mono leading-relaxed break-all">
                  curl -fsSL https://raw.githubusercontent.com/jorinyang/ClawShell/main/install.sh | bash
                </code>
              </div>
              {/* Windows */}
              <div className="rounded-lg border border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)] p-3.5">
                <p className="text-[10px] font-medium text-text-quaternary mb-2 uppercase tracking-wider">Windows PowerShell</p>
                <code className="block text-xs text-foreground font-mono leading-relaxed break-all">
                  iwr https://raw.githubusercontent.com/jorinyang/ClawShell/main/install.ps1 | iex
                </code>
              </div>
            </div>
            <div className="mt-3 rounded-lg border border-[rgba(94,106,210,0.15)] bg-[rgba(94,106,210,0.04)] p-3.5">
              <p className="text-[10px] font-medium text-accent mb-2 uppercase tracking-wider">Then start</p>
              <code className="block text-sm text-foreground font-mono font-semibold">
                clawshell-local
              </code>
              <p className="mt-1.5 text-[11px] text-text-tertiary">
                Browser opens at <span className="text-text-secondary">http://localhost:3456/login</span>. Register or login — done.
              </p>
            </div>
          </div>

          {/* ── Quick links ─────────────────────────────── */}
          <div className="flex items-center justify-center gap-4 mt-6">
            <a
              href="https://github.com/jorinyang/ClawShell"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-text-quaternary hover:text-text-secondary transition-colors"
            >
              <ExternalLink className="h-3 w-3" /> GitHub
            </a>
            <a
              href="https://github.com/jorinyang/ClawShell/blob/main/USER_GUIDE.md"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-text-quaternary hover:text-text-secondary transition-colors"
            >
              <ExternalLink className="h-3 w-3" /> User Guide
            </a>
            <a
              href="https://github.com/jorinyang/ClawShell/releases"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-text-quaternary hover:text-text-secondary transition-colors"
            >
              <ExternalLink className="h-3 w-3" /> Releases
            </a>
          </div>
        </div>
      </main>

      {/* ── Feature Grid ────────────────────────────────── */}
      <section className="px-4 pb-16">
        <div className="mx-auto max-w-[720px] grid grid-cols-2 gap-3">
          <FeatureCard
            icon={<Terminal className="h-4 w-4" />}
            title="One Command"
            desc="Single curl/iwr installs everything. clawshell-local starts API + Web UI + opens browser."
          />
          <FeatureCard
            icon={<Cpu className="h-4 w-4" />}
            title="16-Page GUI"
            desc="Login, register, agents dashboard, skills/knowledge management, task board, admin panel."
          />
          <FeatureCard
            icon={<Layers className="h-4 w-4" />}
            title="4-Layer Exoskeleton"
            desc="L1 self-perception → L2 self-adaptation → L3 self-organization → L4 multi-agent cluster."
          />
          <FeatureCard
            icon={<Shield className="h-4 w-4" />}
            title="5-Way Injection"
            desc="MCP + Hook + Config + Loop Skill + Skill — zero-config auto-injection into any agent framework."
          />
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────── */}
      <footer className="px-6 py-4 border-t border-[rgba(255,255,255,0.04)] text-center">
        <p className="text-[10px] text-text-quaternary">
          ClawShell v3.0.0 &middot; MIT License &middot;{" "}
          <a href="https://github.com/jorinyang/ClawShell" className="hover:text-text-tertiary">github.com/jorinyang/ClawShell</a>
        </p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="rounded-lg border border-[rgba(255,255,255,0.04)] bg-[rgba(255,255,255,0.01)] p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-accent">{icon}</span>
        <span className="text-xs font-medium text-foreground">{title}</span>
      </div>
      <p className="text-[11px] text-text-tertiary leading-relaxed">{desc}</p>
    </div>
  );
}
