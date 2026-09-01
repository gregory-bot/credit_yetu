import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FileSpreadsheet, FileText } from "lucide-react";
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
} from "@/components/ui-bits";
import { api, describeError, downloadReport } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/statements/$referenceId")({
  head: () => ({
    meta: [{ title: "Statement — Credit Yetu" }],
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

function money(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  return `KSh ${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function ratio(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : v.toFixed(2);
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
              Processing — status: <span className="capitalize">{status.data.status}</span>. This
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
          <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
            <SectionCard title="Credit score">
              <ScoreGauge
                score={score.data.score_data.credit_score}
                grade={score.data.score_data.grade}
              />
              <div className="mt-4 border-t border-border pt-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  Affordability
                </p>
                <p className="num mt-1 text-lg font-semibold">
                  {money(score.data.score_data.affordability?.low)} –{" "}
                  {money(score.data.score_data.affordability?.high)}
                </p>
              </div>
              <div className="mt-3">
                <StatusBadge status={status.data?.status ?? ""} />
              </div>
            </SectionCard>

            <div className="space-y-6">
              <SectionCard title="Account">
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

              <SectionCard title="Important ratios">
                <KeyValue
                  items={[
                    ["Debt to income", ratio(ratios.debt_to_income)],
                    ["Income volatility", ratio(ratios.income_volatility)],
                    ["Betting to income", ratio(ratios.betting_to_income)],
                    ["Expenses to income", ratio(ratios.expenses_to_income)],
                  ]}
                />
              </SectionCard>
            </div>
          </div>

          <SectionCard title="Authenticity check">
            <KeyValue
              items={[
                ["Risk score", `${score.data.fraud_data?.risk_score ?? "—"} / 100`],
                ["Risk level", score.data.fraud_data?.risk_level?.toUpperCase()],
                [
                  "Signals",
                  (score.data.fraud_data?.reasons ?? []).join("; ") ||
                    "No tampering signals detected.",
                ],
              ]}
            />
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
            <div className="space-y-2">
              {(score.data.reason_codes ?? []).map((rc: any) => (
                <div
                  key={rc.code}
                  className="flex items-start justify-between gap-4 border-b border-border py-2 text-sm last:border-0"
                >
                  <div>
                    <p className="font-medium">{rc.reason}</p>
                    <p className="text-xs text-muted-foreground">{rc.detail}</p>
                  </div>
                  <span
                    className={`num shrink-0 font-semibold ${rc.points > 0 ? "text-success" : rc.points < 0 ? "text-danger" : "text-muted-foreground"}`}
                  >
                    {rc.points > 0 ? `+${rc.points}` : rc.points}
                  </span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard
            title={`Flagged transactions (${flagged.length})`}
            description="Every flag traces to a rule — self-transfer, a one-off amount outside the normal pattern, or a distress keyword."
          >
            {flagged.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-brand/15 text-left text-xs uppercase tracking-wide">
                      <th className="rounded-l-md px-3 py-2 font-semibold">Date</th>
                      <th className="px-3 py-2 font-semibold">Description</th>
                      <th className="px-3 py-2 font-semibold">Amount</th>
                      <th className="rounded-r-md px-3 py-2 font-semibold">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {flagged.map((t, i) => (
                      <tr key={i} className="border-b border-border last:border-0 align-top">
                        <td className="px-3 py-2.5 text-xs text-muted-foreground">
                          {t.date ? new Date(t.date).toLocaleDateString() : "—"}
                        </td>
                        <td className="px-3 py-2.5">{t.description}</td>
                        <td className="num px-3 py-2.5">{money(t.paid_in || t.withdrawn)}</td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground">
                          {t.flag_reason}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="Nothing flagged"
                description="No transactions on this statement needed a second look."
              />
            )}
          </SectionCard>

          {score.data.ml_shadow && (
            <SectionCard
              title="ML shadow model"
              description="Non-authoritative — never affects the score or affordability above."
            >
              {score.data.ml_shadow.status === "shadow" ? (
                <KeyValue
                  items={[
                    ["Model version", score.data.ml_shadow.model_version],
                    ["Predicted", score.data.ml_shadow.predicted_label],
                    ["Probability of default", score.data.ml_shadow.probability_of_default],
                  ]}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  {score.data.ml_shadow.reason ?? "Not available yet."}
                </p>
              )}
            </SectionCard>
          )}
        </div>
      )}
    </AppPage>
  );
}
