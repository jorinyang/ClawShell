"use client";

export default function SkillsPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-lg font-medium text-foreground">Skills</h1>
        <p className="mt-1 text-xs text-text-quaternary">
          Skill libraries synced from your GitHub repos. Skills installed are available to all your AI agents.
        </p>
      </div>

      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-border">
        <div className="text-center">
          <p className="text-sm text-text-tertiary">Skill management coming soon</p>
          <p className="mt-1 text-xs text-text-quaternary">
            Skills are stored in your {"{prefix}"}-skills GitHub repo and synced automatically
          </p>
        </div>
      </div>
    </div>
  );
}
