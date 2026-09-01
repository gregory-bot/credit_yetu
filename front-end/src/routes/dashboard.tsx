import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorNote, SectionCard, Stat, StatusBadge } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard · Credit Yetu" },
      {
        name: "description",
        content:
          "Portfolio overview: customers scored, statements processed, average credit score and grade distribution.",
      },
      { property: "og:title", content: "Dashboard · Credit Yetu" },
      { property: "og:description", content: "Your lending portfolio at a glance." },
    ],
  }),
  component: Dashboard,
});

// Real grade bands from app/services/scoring/engine.py::_GRADE_BANDS — kept
// in this exact order (best to worst) so the pie chart's colors read as a
// gradient, not fabricated: scores/grades come from GET /statements, never
// derived client-side.
const GRADE_ORDER = ["AA", "A", "BB", "B", "CC", "C", "DD", "D"];
const GRADE_COLORS = [
  "var(--success)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--warning)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--danger)",
  "oklch(0.4 0.15 25)",
];

type StatementRow = {
  reference_id: string;
  statement_type: string;
  status: string;
  national_id: string | null;
  account_holder: string | null;
  needs_review: boolean;
  created_at: string;
  score: { credit_score: number; grade: string } | null;
};

function Dashboard() {
  const { ready, isAuthenticated } = useRequireAuth();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [statementType, setStatementType] = useState("all");

  const customers = useQuery({
    queryKey: ["customers"],
    enabled: ready && isAuthenticated,
    queryFn: () => api<any[]>("/customers"),
  });

  const statements = useQuery({
    queryKey: ["statements", null],
    enabled: ready && isAuthenticated,
    queryFn: () => api<StatementRow[]>("/statements"),
  });

  const rows = useMemo(() => statements.data ?? [], [statements.data]);

  const filtered = useMemo(() => {
    return rows.filter((s) => {
      const created = new Date(s.created_at);
      if (from && created < new Date(from)) return false;
      if (to && created > new Date(`${to}T23:59:59`)) return false;
      if (statementType !== "all" && s.statement_type !== statementType) return false;
      return true;
    });
  }, [rows, from, to, statementType]);

  const scored = filtered.filter((s) => s.score);
  const avgScore = scored.length
    ? Math.round(scored.reduce((sum, s) => sum + (s.score?.credit_score ?? 0), 0) / scored.length)
    : 0;

  const gradeData = useMemo(() => {
    const counts: Record<string, number> = {};
    scored.forEach((s) => {
      const g = s.score!.grade;
      counts[g] = (counts[g] ?? 0) + 1;
    });
    return GRADE_ORDER.filter((g) => counts[g]).map((g) => ({ name: g, value: counts[g] }));
  }, [scored]);

  const scoreBuckets = useMemo(() => {
    const buckets = [
      { name: "300–450", min: 300, max: 450 },
      { name: "450–600", min: 450, max: 600 },
      { name: "600–750", min: 600, max: 750 },
      { name: "750–900", min: 750, max: 901 },
    ];
    return buckets.map((b) => ({
      name: b.name,
      count: scored.filter((s) => {
        const v = s.score!.credit_score;
        return v >= b.min && v < b.max;
      }).length,
    }));
  }, [scored]);

  const monthly = useMemo(() => {
    const counts: Record<string, number> = {};
    filtered.forEach((s) => {
      const d = new Date(s.created_at);
      if (Number.isNaN(d.valueOf())) return;
      const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      counts[k] = (counts[k] ?? 0) + 1;
    });
    return Object.entries(counts)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-6)
      .map(([name, uploads]) => ({ name, uploads }));
  }, [filtered]);

  const needsReview = filtered.filter((s) => s.status === "needs_review").length;
  const thisMonth = filtered.filter((s) => {
    const d = new Date(s.created_at);
    const now = new Date();
    return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  }).length;

  if (!ready || !isAuthenticated) return null;

  return (
    <AppPage
      title="Dashboard"
      description="Portfolio overview across everything your team has scored."
      actions={
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link to="/statements">Upload statement</Link>
          </Button>
          <Button asChild className="bg-danger text-danger-foreground hover:bg-danger/90">
            <Link to="/verify">Verify a client</Link>
          </Button>
        </div>
      }
    >
      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <aside className="space-y-4">
          <SectionCard title="Filters">
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="from" className="text-xs">
                  From
                </Label>
                <Input
                  id="from"
                  type="date"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="to" className="text-xs">
                  To
                </Label>
                <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Statement type</Label>
                <div className="flex flex-col gap-1">
                  {["all", "mpesa", "bank", "till", "paybill", "sacco"].map((p) => (
                    <button
                      key={p}
                      onClick={() => setStatementType(p)}
                      className={`rounded-md px-2.5 py-1.5 text-left text-xs font-medium capitalize transition-colors ${
                        statementType === p
                          ? "bg-brand/20 text-foreground"
                          : "text-muted-foreground hover:bg-muted"
                      }`}
                    >
                      {p === "all" ? "All types" : p}
                    </button>
                  ))}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={() => {
                  setFrom("");
                  setTo("");
                  setStatementType("all");
                }}
              >
                Reset filters
              </Button>
            </div>
          </SectionCard>
        </aside>

        <div className="space-y-6">
          {(customers.isError || statements.isError) && (
            <ErrorNote message={describeError(customers.error ?? statements.error)} />
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat
              label="Customers"
              value={customers.data?.length ?? 0}
              hint="registered profiles"
            />
            <Stat label="Processed this month" value={thisMonth} hint="statements uploaded" />
            <Stat
              label="Average score"
              value={avgScore || "—"}
              tone={
                avgScore >= 650
                  ? "success"
                  : avgScore >= 500
                    ? "warning"
                    : avgScore
                      ? "danger"
                      : "neutral"
              }
              hint="300–900 range"
            />
            <Stat
              label="Needs review"
              value={needsReview}
              tone={needsReview ? "warning" : "neutral"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Grade distribution">
              {gradeData.length ? (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={gradeData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {gradeData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={GRADE_COLORS[GRADE_ORDER.indexOf(entry.name) % GRADE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Legend />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState
                  title="No graded statements yet"
                  description="Upload a statement to generate your first score."
                />
              )}
            </SectionCard>

            <SectionCard title="Score distribution">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={scoreBuckets}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--brand)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>

          <SectionCard title="Monthly volume" description="Statements uploaded per month">
            {monthly.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={monthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="uploads" fill="var(--success)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState
                title="No volume data"
                description="Monthly counts appear once statements have been uploaded."
              />
            )}
          </SectionCard>

          <SectionCard
            title="Recent statements"
            action={
              <Button asChild variant="ghost" size="sm">
                <Link to="/statements">View all</Link>
              </Button>
            }
          >
            {filtered.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-brand/15 text-left text-xs uppercase tracking-wide">
                      <th className="rounded-l-md px-3 py-2 font-semibold">Customer</th>
                      <th className="px-3 py-2 font-semibold">Type</th>
                      <th className="px-3 py-2 font-semibold">Status</th>
                      <th className="rounded-r-md px-3 py-2 font-semibold">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 8).map((s) => (
                      <tr key={s.reference_id} className="border-b border-border last:border-0">
                        <td className="px-3 py-2.5 font-medium">
                          {s.account_holder ?? s.national_id ?? "—"}
                        </td>
                        <td className="px-3 py-2.5 uppercase text-muted-foreground">
                          {s.statement_type}
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={s.status} />
                        </td>
                        <td className="num px-3 py-2.5">
                          {s.score ? `${s.score.credit_score} · ${s.score.grade}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No statements yet"
                description="Upload your first statement to start building a portfolio."
                action={
                  <Button asChild className="bg-danger text-danger-foreground hover:bg-danger/90">
                    <Link to="/statements">Upload statement</Link>
                  </Button>
                }
              />
            )}
          </SectionCard>
        </div>
      </div>
    </AppPage>
  );
}
