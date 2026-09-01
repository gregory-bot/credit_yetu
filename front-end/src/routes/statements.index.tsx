import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Plus, Upload } from "lucide-react";
import { toast } from "sonner";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorNote, SectionCard, StatusBadge } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/statements/")({
  validateSearch: (search: Record<string, unknown>): { national_id?: string | undefined } => ({
    national_id: typeof search["national_id"] === "string" ? search["national_id"] : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Statements · Credit Yetu" },
      {
        name: "description",
        content: "Upload M-Pesa, bank, till, paybill or SACCO statements and track scoring.",
      },
    ],
  }),
  component: StatementsPage,
});

type StatementRow = {
  reference_id: string;
  statement_type: string;
  status: string;
  national_id: string | null;
  account_holder: string | null;
  needs_review: boolean;
  created_at: string;
  score: { credit_score: number; grade: string; limit_low: number; limit_high: number } | null;
};

const PRODUCTS = [
  "personal",
  "employed",
  "business_registered",
  "business_unregistered",
  "sme",
  "vehicle",
] as const;
const STATEMENT_TYPES = ["mpesa", "bank", "till", "paybill", "sacco"] as const;

function StatementsPage() {
  const { national_id } = Route.useSearch();
  const { ready, isAuthenticated } = useRequireAuth();
  const [open, setOpen] = useState(false);

  const statements = useQuery({
    queryKey: ["statements", national_id ?? null],
    enabled: ready && isAuthenticated,
    queryFn: () =>
      api<StatementRow[]>(
        national_id ? `/statements?national_id=${encodeURIComponent(national_id)}` : "/statements",
      ),
  });

  const rows = useMemo(() => statements.data ?? [], [statements.data]);

  if (!ready || !isAuthenticated) return null;

  return (
    <AppPage
      title="Statements"
      description={
        national_id
          ? `Filtered to national ID ${national_id}`
          : "Every statement your team has uploaded."
      }
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-danger text-danger-foreground hover:bg-danger/90">
              <Upload className="size-4" /> Upload statement
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Upload a statement</DialogTitle>
            </DialogHeader>
            <UploadForm defaultNationalId={national_id} onDone={() => setOpen(false)} />
          </DialogContent>
        </Dialog>
      }
    >
      <div className="space-y-6">
        {national_id && (
          <Button asChild variant="ghost" size="sm">
            <Link to="/statements" search={{}}>
              ← Clear filter
            </Link>
          </Button>
        )}
        {statements.isError && <ErrorNote message={describeError(statements.error)} />}

        <SectionCard title={`${rows.length} statement${rows.length === 1 ? "" : "s"}`}>
          {rows.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-brand/15 text-left text-xs uppercase tracking-wide">
                    <th className="rounded-l-md px-3 py-2 font-semibold">Customer</th>
                    <th className="px-3 py-2 font-semibold">Type</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Score</th>
                    <th className="px-3 py-2 font-semibold">Uploaded</th>
                    <th className="rounded-r-md px-3 py-2 font-semibold" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s) => (
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
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <Button asChild size="sm" variant="ghost">
                          <Link
                            to="/statements/$referenceId"
                            params={{ referenceId: s.reference_id }}
                          >
                            View
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No statements yet"
              description="Upload an M-Pesa, bank, till, paybill or SACCO statement to generate your first score."
              action={
                <Button
                  className="bg-danger text-danger-foreground hover:bg-danger/90"
                  onClick={() => setOpen(true)}
                >
                  <Plus className="size-4" /> Upload statement
                </Button>
              }
            />
          )}
        </SectionCard>
      </div>
    </AppPage>
  );
}

function UploadForm({
  defaultNationalId,
  onDone,
}: {
  defaultNationalId?: string | undefined;
  onDone: () => void;
}) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [statementType, setStatementType] = useState<(typeof STATEMENT_TYPES)[number]>("mpesa");
  const [product, setProduct] = useState<(typeof PRODUCTS)[number]>("personal");
  const [nationalId, setNationalId] = useState(defaultNationalId ?? "");
  const [crbObligation, setCrbObligation] = useState("0");
  const [bankCode, setBankCode] = useState("");
  const [passcode, setPasscode] = useState("");

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a statement file first.");
      const form = new FormData();
      form.append("file", file);
      form.append("statement_type", statementType);
      form.append("product", product);
      form.append("crb_obligation", crbObligation || "0");
      if (nationalId) form.append("national_id", nationalId);
      if (bankCode) form.append("bank_code", bankCode);
      if (passcode) form.append("passcode", passcode);
      return api<{ reference_id: string }>("/statements/upload", { method: "POST", form });
    },
    onSuccess: (data) => {
      toast.success("Statement received. Scoring now.");
      onDone();
      navigate({ to: "/statements/$referenceId", params: { referenceId: data.reference_id } });
    },
    onError: (err) => toast.error(describeError(err)),
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        upload.mutate();
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="file">Statement file (PDF, PNG or JPG)</Label>
        <Input
          id="file"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          required
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>Statement type</Label>
          <Select
            value={statementType}
            onValueChange={(v) => setStatementType(v as typeof statementType)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATEMENT_TYPES.map((t) => (
                <SelectItem key={t} value={t} className="capitalize">
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Product</Label>
          <Select value={product} onValueChange={(v) => setProduct(v as typeof product)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRODUCTS.map((p) => (
                <SelectItem key={p} value={p} className="capitalize">
                  {p.replace(/_/g, " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="national_id">National ID (links to an existing customer, if any)</Label>
        <Input
          id="national_id"
          value={nationalId}
          onChange={(e) => setNationalId(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="crb">Existing CRB obligation (KSh)</Label>
          <Input
            id="crb"
            type="number"
            min={0}
            value={crbObligation}
            onChange={(e) => setCrbObligation(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="bank_code">Bank code (bank statements only)</Label>
          <Input
            id="bank_code"
            value={bankCode}
            onChange={(e) => setBankCode(e.target.value)}
            placeholder="e.g. SCB"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="passcode">PDF passcode (if the file is encrypted)</Label>
        <Input
          id="passcode"
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          type="password"
        />
      </div>

      <Button
        type="submit"
        disabled={upload.isPending}
        className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
      >
        {upload.isPending ? "Uploading…" : "Upload & score"}
      </Button>
    </form>
  );
}
