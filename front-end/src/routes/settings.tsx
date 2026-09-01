import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Check, Copy, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { AppPage } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorNote, KeyValue, SectionCard } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { getOfficerName, setOfficerName, useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [{ title: "Settings · Credit Yetu" }],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const [officer, setOfficer] = useState(getOfficerName());
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const me = useQuery({
    queryKey: ["me"],
    enabled: ready && isAuthenticated,
    queryFn: () => api<any>("/auth/me"),
  });

  const generateKey = useMutation({
    mutationFn: () => api<any>("/auth/api-keys", { method: "POST", body: { label: "manual" } }),
    onSuccess: (data) => {
      setIssuedKey(data.api_key);
      toast.success("New API key created");
    },
    onError: (err) => toast.error(describeError(err)),
  });

  if (!ready || !isAuthenticated) return null;

  return (
    <AppPage title="Settings" description="Organization details, consent defaults, and API access.">
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Organization">
          {me.isError && <ErrorNote message={describeError(me.error)} />}
          {me.data && (
            <KeyValue
              items={[
                ["Name", me.data.name],
                ["Email", me.data.email],
                ["Account type", <span className="capitalize">{me.data.account_type}</span>],
                ["Wallet balance", `KSh ${Number(me.data.wallet_balance ?? 0).toLocaleString()}`],
              ]}
            />
          )}
        </SectionCard>

        <SectionCard
          title="Consent default"
          description="Pre-fills 'consent collected by' on the Verify page."
        >
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-2">
              <Label htmlFor="officer">Your name</Label>
              <Input id="officer" value={officer} onChange={(e) => setOfficer(e.target.value)} />
            </div>
            <Button
              variant="outline"
              onClick={() => {
                setOfficerName(officer.trim());
                toast.success("Saved");
              }}
            >
              Save
            </Button>
          </div>
        </SectionCard>

        <SectionCard
          title="API keys"
          description="For programmatic access, separate from your dashboard password."
          className="lg:col-span-2"
        >
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Every API request is authorized with a Bearer key, not your password. Generate one
              here for scripts or a server-to-server integration.
            </p>
            <Button
              variant="outline"
              disabled={generateKey.isPending}
              onClick={() => generateKey.mutate()}
            >
              <KeyRound className="size-4" />{" "}
              {generateKey.isPending ? "Generating…" : "Generate new API key"}
            </Button>

            {issuedKey && (
              <div className="rounded-xl border border-success/30 bg-success/5 p-4">
                <p className="text-xs text-muted-foreground">
                  Shown <strong className="text-danger">once</strong>. Copy it now.
                </p>
                <div className="num mt-2 break-all rounded-lg border border-border bg-card p-3 text-xs">
                  {issuedKey}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={async () => {
                    await navigator.clipboard.writeText(issuedKey);
                    setCopied(true);
                    toast.success("Copied");
                  }}
                >
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
            )}
          </div>
        </SectionCard>
      </div>
    </AppPage>
  );
}
