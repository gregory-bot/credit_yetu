import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FileSpreadsheet, FileText, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  ErrorNote,
  KeyValue,
  ScoreGauge,
  SectionCard,
  StatusBadge,
  toneForStatus,
} from "@/components/ui-bits";
import { cn } from "@/lib/utils";
import { api, describeError, downloadReport } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/statements/$referenceId")({
  head: () => ({
    meta: [{ title: "Statement · Credit Yetu" }],
  }),
  component: StatementDetail,
});

type StatementStatus = {
  reference_id: string;
  status: string;
  statement_type: string;
  extraction_method: string | null;
  needs_review: boolean;
  status_message: string | null;
  account_holder: string | null;
  transaction_count: number;
  scored: boolean;
};

const TERMINAL_STATUSES = ["scored", "needs_review", "failed"];
// A genuine multi-line narration only ever runs a sentence or two. Past this,
// a description is almost certainly a parsing artefact (see the backend's
// _MAX_DESCRIPTION_LEN guard) — collapse it behind a toggle instead of
// stretching the whole row.
const DESCRIPTION_PREVIEW_LEN = 140;

function money(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `KSh ${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function ratio(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : v.toFixed(2);
}

function Description({ text }: { text: string }) {
  if (text.length <= DESCRIPTION_PREVIEW_LEN) {
    return <p className="break-words text-sm">{text || "—"}</p>;
  }
  return (
    <details className="group">
      <summary className="cursor-pointer break-words text-sm marker:content-none">
        {text.slice(0, DESCRIPTION_PREVIEW_LEN)}
        <span className="text-muted-foreground">…</span>{" "}
        <span className="text-xs font-medium text-brand underline decoration-dotted group-open:hidden">
          Show full text
        </span>
      </summary>
      <p className="mt-1 break-words font-mono text-xs leading-relaxed text-muted-foreground">
        {text}
      </p>
    </details>
  );
}

function StatementDetail() {
  const { referenceId } = Route.useParams();
  const { ready, isAuthenticated } = useRequireAuth();

  const status = useQuery({
    queryKey: ["statement", referenceId],
    enabled: ready && isAuthenticated,
    queryFn: () => api<StatementStatus>(`/statements/${referenceId}`),
    refetchInterval: (query) =>
      TERMINAL_STATUSES.includes(query.state.data?.status ?? "") ? false : 2500,
  });

  const isTerminal = TERMINAL_STATUSES.includes(status.data?.status ?? "");

  const score = useQuery({
    queryKey: ["statement-score", referenceId],
    enabled: ready && isAuthenticated && isTerminal,
    queryFn: () => api<any>(`/statements/${referenceId}/score`),
  });

  const transactions = useQuery({
    queryKey: ["statement-transactions", referenceId],
    enabled: ready && isAuthenticated && isTerminal,
    queryFn: () => api<any[]>(`/statements/${referenceId}/transactions`),
  });

  // financial_summary lives on a separate endpoint from /score — not the
  // same payload, so it needs its own fetch.
  const summary = useQuery({
    queryKey: ["statement-summary", referenceId],
    enabled: ready && isAuthenticated && isTerminal,
    queryFn: () => api<{ financial_summary: any }>(`/statements/${referenceId}/summary`),
  });

  if (!ready || !isAuthenticated) return null;

  const flagged = (transactions.data ?? []).filter((t) => t.is_flagged);
  const monthlyRows: any[] = summary.data?.financial_summary?.monthly_detail?.rows ?? [];
  const ratios = score.data?.score_breakdown?.ratios ?? {};
  const riskLevel: string | undefined = score.data?.fraud_data?.risk_level;
  const riskScore: number = score.data?.fraud_data?.risk_score ?? 0;
  const riskTone = toneForStatus(riskLevel);

  return (
    <AppPage
      title="Statement detail"
      description={referenceId}
      actions={
        isTerminal && score.data ? (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() =>
                downloadReport(referenceId, "pdf").catch((e) => toast.error(describeError(e)))
              }
            >
              <FileText className="size-4" /> PDF
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                downloadReport(referenceId, "excel").catch((e) => toast.error(describeError(e)))
              }
            >
              <FileSpreadsheet className="size-4" /> Excel
            </Button>
          </div>
        ) : undefined
      }
    >
      {status.isError && <ErrorNote message={describeError(status.error)} />}

      {!isTerminal && status.data && (
        <SectionCard>
          <div className="flex items-center gap-3">
            <span className="size-2.5 animate-pulse rounded-full bg-warning" />
            <p className="text-sm font-medium">
              Processing. Status: <span className="capitalize">{status.data.status}</span>. This
              page updates automatically.
            </p>
          </div>
        </SectionCard>
      )}

      {status.data?.status === "failed" && (
        <ErrorNote message={status.data.status_message ?? "Processing failed."} />
      )}

      {isTerminal && score.data && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
            <SectionCard className="bg-gradient-to-b from-brand/10 to-card">
              <div className="flex flex-col items-center text-center">
                <ScoreGauge
                  score={score.data.score_data.credit_score}
                  grade={score.data.score_data.grade}
                />
                <StatusBadge status={status.data?.status ?? ""} className="mt-2" />
              </div>
              <div className="mt-5 rounded-xl border border-border bg-background/60 p-4 text-center">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Affordability
                </p>
                <p className="num mt-1 text-xl font-bold">
                  {money(score.data.score_data.affordability?.low)}
                  <span className="mx-1 font-normal text-muted-foreground">to</span>
                  {money(score.data.score_data.affordability?.high)}
                </p>
              </div>
            </SectionCard>

            <div className="grid gap-6 sm:grid-cols-2">
              <SectionCard title="Account" className="sm:col-span-2">
                <KeyValue
                  items={[
                    ["Account holder", status.data?.account_holder],
                    ["Statement type", status.data?.statement_type?.toUpperCase()],
                    ["Avg monthly income", money(score.data.score_data.avg_monthly_income)],
                    ["Statement months", score.data.score_data.month_count?.toFixed(2)],
                    ["Extraction method", status.data?.extraction_method],
                    ["Transactions", status.data?.transaction_count],
                  ]}
                />
              </SectionCard>

              <div className="grid grid-cols-2 gap-3 sm:col-span-2 sm:grid-cols-4">
                {[
                  ["Debt to income", ratios.debt_to_income],
                  ["Income volatility", ratios.income_volatility],
                  ["Betting to income", ratios.betting_to_income],
                  ["Expenses to income", ratios.expenses_to_income],
                ].map(([label, value]) => (
                  <div
                    key={label as string}
                    className="rounded-xl border border-border bg-card p-4 shadow-card"
                  >
                    <p className="text-[11px] font-medium uppercase leading-tight tracking-wide text-muted-foreground">
                      {label}
                    </p>
                    <p className="num mt-1.5 text-lg font-semibold">{ratio(value as number)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <SectionCard
            title="Authenticity check"
            action={
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <ShieldCheck className="size-3.5" /> Risk {riskScore} / 100
              </span>
            }
          >
            <div className="flex flex-wrap items-center gap-4">
              <StatusBadge status={riskLevel ?? "unknown"} tone={riskTone} />
              <div className="h-1.5 min-w-[160px] flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full",
                    riskTone === "success"
                      ? "bg-success"
                      : riskTone === "warning"
                        ? "bg-warning"
                        : riskTone === "danger"
                          ? "bg-danger"
                          : "bg-muted-foreground",
                  )}
                  style={{ width: `${Math.min(100, Math.max(0, riskScore))}%` }}
                />
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              {(score.data.fraud_data?.reasons ?? []).join("; ") ||
                "No tampering signals detected."}
            </p>
          </SectionCard>

          {monthlyRows.length > 0 && (
            <SectionCard title="Monthly financial summary">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-brand/15 text-left text-xs uppercase tracking-wide">
                      <th className="rounded-l-md px-3 py-2 font-semibold">Month</th>
                      <th className="px-3 py-2 font-semibold">Credits</th>
                      <th className="px-3 py-2 font-semibold">Debits</th>
                      <th className="px-3 py-2 font-semibold">Net (CR)</th>
                      <th className="rounded-r-md px-3 py-2 font-semibold">Net (DR)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthlyRows.map((r) => (
                      <tr key={r.month} className="border-b border-border last:border-0">
                        <td className="px-3 py-2.5 font-medium">{r.month}</td>
                        <td className="num px-3 py-2.5">{money(r.credits)}</td>
                        <td className="num px-3 py-2.5">{money(r.debits)}</td>
                        <td className="num px-3 py-2.5">{money(r.net_credit)}</td>
                        <td className="num px-3 py-2.5">{money(r.net_debit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          )}

          <SectionCard
            title="Score reasons"
            description="Every point on the score traces to one of these rules."
          >
            <div className="space-y-1">
              {(score.data.reason_codes ?? []).map((rc: any) => (
                <div
                  key={rc.code}
                  className="flex items-start gap-3 border-b border-border py-2.5 last:border-0"
                >
                  <span
                    className={cn(
                      "num mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold",
                      rc.points > 0
                        ? "bg-success/10 text-success"
                        : rc.points < 0
                          ? "bg-danger/10 text-danger"
                          : "bg-muted text-muted-foreground",
                    )}
                  >
                    {rc.points > 0 ? `+${rc.points}` : rc.points}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{rc.reason}</p>
                    <p className="text-xs text-muted-foreground">{rc.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title={`Flagged transactions (${flagged.length})`}
            description="Every flag traces to a rule: self-transfer, a one-off amount outside the normal pattern, or a distress keyword."
          >
            {flagged.length ? (
              <div className="space-y-3">
                {flagged.map((t, i) => (
                  <div key={i} className="rounded-xl border border-warning/30 bg-warning/5 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-start gap-2.5">
                        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[color:oklch(0.6_0.13_74.5)]" />
                        <div className="min-w-0">
                          <Description text={t.description ?? ""} />
                          <p className="mt-1 text-xs text-muted-foreground">
                            {t.date ? new Date(t.date).toLocaleDateString() : "No date on record"}
                          </p>
                        </div>
                      </div>
                      <span className="num shrink-0 text-sm font-semibold">
                        {money(t.paid_in || t.withdrawn)}
                      </span>
                    </div>
                    <p className="mt-2 inline-block rounded-full bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                      {t.flag_reason}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Nothing flagged"
                description="No transactions on this statement needed a second look."
              />
            )}
          </SectionCard>
        </div>
      )}
    </AppPage>
  );
}
