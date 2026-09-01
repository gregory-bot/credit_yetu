import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, describeError } from "@/lib/api";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (search: Record<string, unknown>): { token?: string | undefined } => ({
    token: typeof search["token"] === "string" ? search["token"] : undefined,
  }),
  head: () => ({
    meta: [{ title: "Reset password — Credit Yetu" }],
  }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);

  const reset = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error("This reset link is missing its token.");
      if (password.length < 8) throw new Error("Password must be at least 8 characters.");
      if (password !== confirm) throw new Error("Passwords don't match.");
      return api<any>("/auth/reset-password", {
        method: "POST",
        auth: false,
        body: { token, new_password: password },
      });
    },
    onSuccess: () => {
      setDone(true);
      toast.success("Password updated");
    },
    onError: (err) => toast.error(describeError(err)),
  });

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md">
        <div className="flex justify-center">
          <Logo />
        </div>

        {!token ? (
          <div className="mt-8 rounded-xl border border-danger/30 bg-danger/5 p-5 text-center">
            <p className="text-sm font-semibold text-danger">Invalid reset link</p>
            <p className="mt-2 text-xs text-muted-foreground">
              This link is missing its token. Request a new one from the sign-in page.
            </p>
            <Button asChild className="mt-4 w-full">
              <Link to="/login" search={{ mode: "signin" }}>
                Back to sign in
              </Link>
            </Button>
          </div>
        ) : done ? (
          <div className="mt-8 space-y-5">
            <div className="rounded-xl border border-success/30 bg-success/5 p-5 text-center">
              <CheckCircle2 className="mx-auto size-8 text-success" />
              <p className="mt-2 text-sm font-semibold">Password updated</p>
              <p className="mt-1 text-xs text-muted-foreground">
                You can now sign in with your new password.
              </p>
            </div>
            <Button
              className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
              onClick={() => navigate({ to: "/login", search: { mode: "signin" } })}
            >
              Go to sign in
            </Button>
          </div>
        ) : (
          <form
            className="mt-8 space-y-5"
            onSubmit={(e) => {
              e.preventDefault();
              reset.mutate();
            }}
          >
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Choose a new password</h1>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">New password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter your new password"
                autoComplete="new-password"
                required
              />
            </div>
            <Button
              type="submit"
              disabled={reset.isPending}
              className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
            >
              {reset.isPending ? "Updating…" : "Update password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
