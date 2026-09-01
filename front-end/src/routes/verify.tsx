import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { CheckCircle2, IdCard, ScanFace, ShieldCheck, UserRound, XCircle } from "lucide-react";
import { toast } from "sonner";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorNote, KeyValue, SectionCard, StatusBadge } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { getOfficerName, setOfficerName, useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/verify")({
  head: () => ({
    meta: [
      { title: "Verify a client · Credit Yetu" },
      {
        name: "description",
        content: "IPRS identity lookup, face match against an ID photo, and CRB/KRA checks.",
      },
    ],
  }),
  component: VerifyPage,
});

type CheckResult = {
  label: string;
  ok: boolean | null;
  data: any;
  sandbox?: boolean;
  provider?: string;
} | null;

function StepTitle({ step, children }: { step: number; children: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand/15 text-xs font-bold text-[color:oklch(0.55_0.12_74.5)]">
        {step}
      </span>
      {children}
    </span>
  );
}

/** Object URL for a locally-chosen file, revoked automatically when it changes or unmounts. */
function useFilePreview(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  return url;
}

function ImagePreview({
  label,
  url,
  icon: Icon,
  aspect,
}: {
  label: string;
  url: string | null;
  icon: typeof IdCard;
  aspect: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div
        className={`mt-1.5 overflow-hidden rounded-xl border ${aspect} ${
          url ? "border-border bg-card shadow-card" : "border-dashed border-border bg-muted/30"
        }`}
      >
        {url ? (
          <img src={url} alt={label} className="size-full object-cover" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-1.5 text-muted-foreground">
            <Icon className="size-6" />
            <span className="text-[11px]">No photo yet</span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * `accept="image/*"` on the file input is only a hint — the OS picker's "All
 * Files" option, or a drag-and-drop, can still hand back a PDF scan of an ID.
 * An `<img>` can't render that (shows a broken-image icon), and a real KYC
 * face-match provider needs actual image bytes too — so reject it here with
 * a clear reason instead of silently producing a dead preview.
 */
function pickImageFile(
  input: HTMLInputElement,
  setFile: (file: File | null) => void,
  label: string,
) {
  const file = input.files?.[0] ?? null;
  if (file && !file.type.startsWith("image/")) {
    toast.error(`${label} must be a photo (JPG or PNG) — "${file.name}" isn't an image.`);
    input.value = "";
    setFile(null);
    return;
  }
  setFile(file);
}

function resultEntries(data: unknown) {
  return Object.entries((data ?? {}) as Record<string, unknown>)
    .filter(([k]) => !["signature", "fingerprint", "photo"].includes(k))
    .slice(0, 8)
    .map(([k, v]): [string, string] => [
      k.replace(/_/g, " "),
      typeof v === "object" ? JSON.stringify(v) : String(v),
    ]);
}

function VerifyPage() {
  const { ready, isAuthenticated } = useRequireAuth();

  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [collectedBy, setCollectedBy] = useState(getOfficerName());
  const [selfie, setSelfie] = useState<File | null>(null);
  const [idImage, setIdImage] = useState<File | null>(null);
  const idImagePreview = useFilePreview(idImage);
  const selfiePreview = useFilePreview(selfie);

  const [identityResult, setIdentityResult] = useState<CheckResult>(null);
  const [faceResult, setFaceResult] = useState<CheckResult>(null);
  const [kraResult, setKraResult] = useState<CheckResult>(null);
  const [crbResult, setCrbResult] = useState<CheckResult>(null);
  const [phoneResult, setPhoneResult] = useState<CheckResult>(null);
  const [pastResult, setPastResult] = useState<{ reference_id: string; data: any } | null>(null);

  const recent = useQuery({
    queryKey: ["verifications"],
    enabled: ready && isAuthenticated,
    queryFn: () => api<any[]>("/verify"),
  });

  const consentPayload = () => {
    const name = collectedBy.trim();
    if (name) setOfficerName(name);
    return { consent, consent_collected_by: name || "Unspecified" };
  };

  function requireConsentAndId(): boolean {
    if (!nationalId.trim()) {
      toast.error("Enter the client's national ID first.");
      return false;
    }
    if (!consent) {
      toast.error("Consent is required before running a verification check.");
      return false;
    }
    if (!collectedBy.trim()) {
      toast.error("Enter who collected consent.");
      return false;
    }
    return true;
  }

  const identity = useMutation({
    mutationFn: () =>
      api<any>("/verify/identity", {
        method: "POST",
        body: { identifier: nationalId, ...consentPayload() },
      }),
    onSuccess: (data) => {
      setIdentityResult({
        label: "Official record (IPRS)",
        ok: true,
        data: data.data,
        sandbox: data.sandbox,
        provider: data.provider,
      });
      recent.refetch();
      toast.success("Identity verified");
    },
    onError: (err) => toast.error(describeError(err)),
  });

  const faceMatch = useMutation({
    mutationFn: () => {
      if (!selfie || !idImage) throw new Error("Upload both a selfie and an ID photo first.");
      const form = new FormData();
      form.append("id_number", nationalId);
      const { consent: c, consent_collected_by } = consentPayload();
      form.append("consent", String(c));
      form.append("consent_collected_by", consent_collected_by);
      form.append("selfie", selfie);
      form.append("national_id_image", idImage);
      return api<any>("/verify/face-match", { method: "POST", form });
    },
    onSuccess: (data) => {
      setFaceResult({
        label: "Face match",
        ok: data.data?.is_match ?? null,
        data: data.data,
        sandbox: data.sandbox,
        provider: data.provider,
      });
      recent.refetch();
    },
    onError: (err) => toast.error(describeError(err)),
  });

  const kraPin = useMutation({
    mutationFn: () =>
      api<any>("/verify/kra-pin", {
        method: "POST",
        body: { identifier: nationalId, search_type: "id", ...consentPayload() },
      }),
    onSuccess: (data) => {
      setKraResult({
        label: "KRA PIN",
        ok: true,
        data: data.data,
        sandbox: data.sandbox,
        provider: data.provider,
      });
      recent.refetch();
    },
    onError: (err) => toast.error(describeError(err)),
  });

  const crbMetropol = useMutation({
    mutationFn: () =>
      api<any>("/verify/crb/metropol", {
        method: "POST",
        body: { identifier: nationalId, full: false, ...consentPayload() },
      }),
    onSuccess: (data) => {
      setCrbResult({
        label: "CRB score (Metropol)",
        ok: true,
        data: data.data,
        sandbox: data.sandbox,
        provider: data.provider,
      });
      recent.refetch();
    },
    onError: (err) => toast.error(describeError(err)),
  });

  const phoneCheck = useMutation({
    mutationFn: () => {
      if (!phone.trim()) throw new Error("Enter a phone number first.");
      return api<any>("/verify/phone/hakikisha", {
        method: "POST",
        body: { identifier: phone, national_id: nationalId, ...consentPayload() },
      });
    },
    onSuccess: (data) => {
      setPhoneResult({
        label: "Phone check",
        ok: data.data?.is_valid ?? null,
        data: data.data,
        sandbox: data.sandbox,
        provider: data.provider,
      });
      recent.refetch();
    },
    onError: (err) => toast.error(describeError(err)),
  });

  if (!ready || !isAuthenticated) return null;

  return (
    <AppPage
      title="Verify a client"
      description="IPRS identity, face match, KRA PIN, CRB and phone checks in one place."
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <SectionCard
            title={<StepTitle step={1}>Client & consent</StepTitle>}
            description="Required before any check can run."
          >
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="national_id">National ID number</Label>
                  <Input
                    id="national_id"
                    value={nationalId}
                    onChange={(e) => setNationalId(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="collected_by">Consent collected by</Label>
                  <Input
                    id="collected_by"
                    value={collectedBy}
                    onChange={(e) => setCollectedBy(e.target.value)}
                    placeholder="Your name"
                  />
                </div>
              </div>
              <label className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 p-3 text-sm">
                <Checkbox
                  checked={consent}
                  onCheckedChange={(v) => setConsent(v === true)}
                  className="mt-0.5"
                />
                <span>
                  The client has consented to identity and credit checks being run against official
                  records.
                </span>
              </label>
            </div>
          </SectionCard>

          <SectionCard title={<StepTitle step={2}>Identity & face match</StepTitle>}>
            <div className="space-y-4">
              <Button
                type="button"
                variant="outline"
                disabled={identity.isPending}
                onClick={() => requireConsentAndId() && identity.mutate()}
              >
                <ShieldCheck className="size-4" />{" "}
                {identity.isPending ? "Checking…" : "Run IPRS identity check"}
              </Button>
              <ResultCard result={identityResult} />

              <div className="grid gap-4 border-t border-border pt-4 sm:grid-cols-[150px_1fr]">
                <div className="flex gap-3 sm:flex-col">
                  <div className="flex-1 sm:flex-none">
                    <ImagePreview
                      label="ID card"
                      url={idImagePreview}
                      icon={IdCard}
                      aspect="aspect-[16/10]"
                    />
                  </div>
                  <div className="flex-1 sm:flex-none">
                    <ImagePreview
                      label="Selfie"
                      url={selfiePreview}
                      icon={UserRound}
                      aspect="aspect-square"
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="id_image">ID card photo</Label>
                      <Input
                        id="id_image"
                        type="file"
                        accept="image/*"
                        onChange={(e) => pickImageFile(e.target, setIdImage, "ID card photo")}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="selfie">Client selfie</Label>
                      <Input
                        id="selfie"
                        type="file"
                        accept="image/*"
                        onChange={(e) => pickImageFile(e.target, setSelfie, "Client selfie")}
                      />
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={faceMatch.isPending}
                    onClick={() => requireConsentAndId() && faceMatch.mutate()}
                  >
                    <ScanFace className="size-4" />{" "}
                    {faceMatch.isPending ? "Matching…" : "Run face match"}
                  </Button>
                  <ResultCard result={faceResult} />
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title={<StepTitle step={3}>Additional checks</StepTitle>}
            description="Each runs independently. Use whichever your policy needs."
          >
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={kraPin.isPending}
                  onClick={() => requireConsentAndId() && kraPin.mutate()}
                >
                  {kraPin.isPending ? "Checking…" : "KRA PIN"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={crbMetropol.isPending}
                  onClick={() => requireConsentAndId() && crbMetropol.mutate()}
                >
                  {crbMetropol.isPending ? "Checking…" : "CRB score"}
                </Button>
              </div>
              <ResultCard result={kraResult} />
              <ResultCard result={crbResult} />

              <div className="border-t border-border pt-4">
                <div className="flex items-end gap-3">
                  <div className="flex-1 space-y-2">
                    <Label htmlFor="phone">Phone number</Label>
                    <Input
                      id="phone"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="2547XXXXXXXX"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={phoneCheck.isPending}
                    onClick={() => requireConsentAndId() && phoneCheck.mutate()}
                  >
                    {phoneCheck.isPending ? "Checking…" : "Check phone"}
                  </Button>
                </div>
                <ResultCard result={phoneResult} />
              </div>
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard title="Recent verifications">
            {recent.isError && <ErrorNote message={describeError(recent.error)} />}
            {recent.data?.length ? (
              <ul className="space-y-1.5">
                {recent.data.slice(0, 15).map((v) => (
                  <li key={v.reference_id}>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-transparent px-2.5 py-2 text-left text-xs transition-colors hover:border-border hover:bg-muted"
                      onClick={async () => {
                        try {
                          const data = await api<any>(`/verify/${v.reference_id}`);
                          setPastResult({ reference_id: v.reference_id, data });
                        } catch (err) {
                          toast.error(describeError(err));
                        }
                      }}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium capitalize">
                          {v.check_type.replace(/_/g, " ")}
                        </span>
                        <span className="num block truncate text-muted-foreground">
                          {v.identifier ?? "—"}
                        </span>
                      </span>
                      <StatusBadge status={v.status ?? "unknown"} className="shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No checks yet"
                description="Results appear here as you run them."
              />
            )}
          </SectionCard>

          {pastResult && (
            <SectionCard
              title={
                <span className="flex items-center gap-2">
                  Selected result
                  {pastResult.data?.sandbox && <SandboxBadge />}
                </span>
              }
            >
              <KeyValue items={resultEntries(pastResult.data?.data ?? pastResult.data)} />
            </SectionCard>
          )}
        </div>
      </div>
    </AppPage>
  );
}

function ResultCard({ result }: { result: CheckResult }) {
  if (!result) return null;
  const badge =
    result.ok === true ? (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-success">
        <CheckCircle2 className="size-3.5" /> Verified
      </span>
    ) : result.ok === false ? (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-danger">
        <XCircle className="size-3.5" /> Mismatch
      </span>
    ) : null;

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {result.label}
          </p>
          {result.sandbox && <SandboxBadge />}
        </div>
        {badge}
      </div>
      {result.sandbox && (
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          Sandbox result — a synthetic response from the built-in mock provider, not a real{" "}
          {result.label.toLowerCase()} lookup. Switch <code className="num">KYC_PROVIDER</code> to a
          live provider to check against real records.
        </p>
      )}
      <div className="mt-2">
        <KeyValue items={resultEntries(result.data)} />
      </div>
    </div>
  );
}

function SandboxBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[color:oklch(0.55_0.12_74.5)]">
      Sandbox
    </span>
  );
}
