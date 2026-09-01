import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "neutral";

export function toneForStatus(status?: string | null): Tone {
  const s = (status ?? "").toLowerCase();
  if (["scored", "verified", "match", "success", "approved", "completed", "low"].includes(s))
    return "success";
  if (["needs_review", "needs review", "pending", "processing", "medium", "review"].includes(s))
    return "warning";
  if (["failed", "mismatch", "error", "high", "critical", "rejected"].includes(s)) return "danger";
  return "neutral";
}

const toneClasses: Record<Tone, string> = {
  success: "bg-success/10 text-success border-success/25",
  warning: "bg-warning/15 text-[color:oklch(0.55_0.12_74.5)] border-warning/40",
  danger: "bg-danger/10 text-danger border-danger/25",
  neutral: "bg-muted text-muted-foreground border-border",
};

export function StatusBadge({
  status,
  tone,
  className,
}: {
  status: string;
  tone?: Tone;
  className?: string;
}) {
  const t = tone ?? toneForStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold capitalize",
        toneClasses[t],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function SectionCard({
  title,
  description,
  action,
  children,
  className,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn("rounded-xl border border-border bg-card shadow-card", className)}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold tracking-tight">{title}</h2>}
            {description && (
              <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: Tone;
}) {
  const accent =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-danger"
        : tone === "warning"
          ? "text-[color:oklch(0.6_0.13_74.5)]"
          : "text-foreground";
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("num mt-2 text-3xl font-semibold", accent)}>{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Semicircular banded credit score gauge (300–900). */
export function ScoreGauge({
  score,
  grade,
  min = 300,
  max = 900,
}: {
  score: number;
  grade?: string;
  min?: number;
  max?: number;
}) {
  const clamped = Math.min(max, Math.max(min, score));
  const pct = (clamped - min) / (max - min);
  const angle = -90 + pct * 180;
  const bands = [
    { color: "var(--danger)", from: 0, to: 0.34 },
    { color: "var(--warning)", from: 0.34, to: 0.67 },
    { color: "var(--success)", from: 0.67, to: 1 },
  ];
  const R = 120;
  const cx = 150;
  const cy = 150;
  const arc = (from: number, to: number) => {
    const a0 = Math.PI * (1 - from);
    const a1 = Math.PI * (1 - to);
    const p0 = [cx + R * Math.cos(a0), cy - R * Math.sin(a0)];
    const p1 = [cx + R * Math.cos(a1), cy - R * Math.sin(a1)];
    return `M ${p0[0]} ${p0[1]} A ${R} ${R} 0 0 1 ${p1[0]} ${p1[1]}`;
  };

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 300 175" className="w-full max-w-[320px]">
        {bands.map((b) => (
          <path
            key={b.from}
            d={arc(b.from, b.to)}
            stroke={b.color}
            strokeWidth={26}
            fill="none"
            strokeLinecap="butt"
          />
        ))}
        <g transform={`rotate(${angle} ${cx} ${cy})`}>
          <line x1={cx} y1={cy} x2={cx} y2={cy - R + 22} stroke="var(--foreground)" strokeWidth={5} strokeLinecap="round" />
        </g>
        <circle cx={cx} cy={cy} r={10} fill="var(--foreground)" />
      </svg>
      <p className="num -mt-2 text-4xl font-bold">{Math.round(score)}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        credit score{grade ? " · grade " : ""}
        {grade && <span className="font-semibold text-foreground">{grade}</span>}
      </p>
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/50 px-6 py-12 text-center">
      <p className="text-sm font-semibold">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
      {message}
    </div>
  );
}

export function KeyValue({ items }: { items: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">{k}</dt>
          <dd className="mt-0.5 text-sm font-medium">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
