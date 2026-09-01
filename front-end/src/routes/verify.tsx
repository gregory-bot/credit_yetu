import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2, ScanFace, ShieldCheck, XCircle } from "lucide-react";
import { toast } from "sonner";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorNote, KeyValue, SectionCard } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { getOfficerName, setOfficerName, useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/verify")({
  head: () => ({
    meta: [
      { title: "Verify a client — Credit Yetu" },
      {
        name: "description",
        content: "IPRS identity lookup, face match against an ID photo, and CRB/KRA checks.",
      },
    ],
  }),
  component: VerifyPage,
});

type CheckResult = { label: string; ok: boolean | null; data: any } | null;

function VerifyPage() {
  const { ready, isAuthenticated } = useRequireAuth();

  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");
  const [consent, setConsent] = useState(false);
  const [collectedBy, setCollectedBy] = useState(getOfficerName());
  const [selfie, setSelfie] = useState<File | null>(null);
  const [idImage, setIdImage] = useState<File | null>(null);

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
      setIdentityResult({ label: "Official record (IPRS)", ok: true, data: data.data });
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
      setFaceResult({ label: "Face match", ok: data.data?.is_match ?? null, data: data.data });
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
      setKraResult({ label: "KRA PIN", ok: true, data: data.data });
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
      setCrbResult({ label: "CRB score (Metropol)", ok: true, data: data.data });
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
      setPhoneResult({ label: "Phone check", ok: data.data?.is_valid ?? null, data: data.data });
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
          <SectionCard title="1. Client & consent" description="Required before any check can run.">
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

          <SectionCard title="2. Identity & face match">
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

              <div className="border-t border-border pt-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="id_image">ID card photo</Label>
                    <Input
                      id="id_image"
                      type="file"
                      accept="image/*"
                      onChange={(e) => setIdImage(e.target.files?.[0] ?? null)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="selfie">Client selfie</Label>
                    <Input
                      id="selfie"
                      type="file"
                      accept="image/*"
                      onChange={(e) => setSelfie(e.target.files?.[0] ?? null)}
                    />
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-3"
                  disabled={faceMatch.isPending}
                  onClick={() => requireConsentAndId() && faceMatch.mutate()}
                >
                  <ScanFace className="size-4" />{" "}
                  {faceMatch.isPending ? "Matching…" : "Run face match"}
                </Button>
                <ResultCard result={faceResult} />
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="3. Additional checks"
            description="Each runs independently — use whichever your policy needs."
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
              <ul className="space-y-1">
                {recent.data.slice(0, 15).map((v) => (
                  <li key={v.reference_id}>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-xs hover:bg-muted"
                      onClick={async () => {
                        try {
                          const data = await api<any>(`/verify/${v.reference_id}`);
                          setPastResult({ reference_id: v.reference_id, data });
                        } catch (err) {
                          toast.error(describeError(err));
                        }
                      }}
                    >
                      <span className="font-medium capitalize">
                        {v.check_type.replace(/_/g, " ")}
                      </span>
                      <span className="num text-muted-foreground">{v.identifier ?? "—"}</span>
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
            <SectionCard title="Selected result">
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-3 text-[11px] leading-relaxed">
                {JSON.stringify(pastResult.data, null, 2)}
              </pre>
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
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {result.label}
        </p>
        {badge}
      </div>
      <KeyValue
        items={Object.entries(result.data ?? {})
          .filter(([k]) => !["signature", "fingerprint", "photo"].includes(k))
          .slice(0, 8)
          .map(([k, v]) => [
            k.replace(/_/g, " "),
            typeof v === "object" ? JSON.stringify(v) : String(v),
          ])}
      />
    </div>
  );
}
