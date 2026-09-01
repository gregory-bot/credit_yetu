import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Building2, Mail, ShieldCheck, User } from "lucide-react";
import { toast } from "sonner";
import authHero from "@/assets/auth-hero.jpg";
import { Logo } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, describeError, setApiKey } from "@/lib/api";
import { setOfficerName } from "@/lib/auth";

type Mode = "signin" | "signup";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { mode: Mode } => ({
    mode: search["mode"] === "signup" ? "signup" : "signin",
  }),
  head: () => ({
    meta: [
      { title: "Sign in — Credit Yetu" },
      {
        name: "description",
        content:
          "Sign in to Credit Yetu or create an individual or company account to start scoring customers.",
      },
      { property: "og:title", content: "Sign in — Credit Yetu" },
      {
        property: "og:description",
        content: "Transparent credit scoring and identity verification, for your whole team.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { mode } = Route.useSearch();
  const navigate = useNavigate();

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden lg:block">
        <img
          src={authHero}
          alt="Loan officer reviewing a customer's credit file"
          width={1024}
          height={1408}
          className="absolute inset-0 size-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[oklch(0.25_0.02_268/0.85)] via-[oklch(0.25_0.02_268/0.25)] to-transparent" />
        <div className="absolute bottom-0 p-10 text-[color:oklch(0.99_0_0)]">
          <h2 className="max-w-md text-3xl font-bold leading-tight">
            Score any customer in minutes.
          </h2>
        </div>
      </div>

      <div className="flex flex-col justify-center bg-background px-6 py-10 sm:px-12">
        <div className="mx-auto w-full max-w-md">
          <Logo />

          <div className="mt-8 flex rounded-full bg-muted p-1">
            {(["signin", "signup"] as const).map((m) => (
              <button
                key={m}
                onClick={() => navigate({ to: "/login", search: { mode: m } })}
                className={`flex-1 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                  mode === m
                    ? "bg-danger text-danger-foreground shadow-card"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          {mode === "signin" ? <SignInForm /> : <SignUpForm />}

          <p className="mt-8 text-center text-xs text-muted-foreground">
            <Link to="/" className="hover:text-foreground">
              ← Back to home
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

function SignInForm() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [forgotMode, setForgotMode] = useState(false);

  const login = useMutation({
    mutationFn: async () =>
      api<any>("/auth/login", { method: "POST", auth: false, body: { email, password } }),
    onSuccess: (data) => {
      if (!data?.api_key) {
        toast.error("Signed in but no session key was returned. Contact support.");
        return;
      }
      setApiKey(data.api_key);
      setOfficerName(data.organization?.name ?? "");
      toast.success(`Welcome back${data.organization?.name ? `, ${data.organization.name}` : ""}`);
      navigate({ to: "/dashboard" });
    },
    onError: (err) => toast.error(describeError(err)),
  });

  if (forgotMode) return <ForgotPasswordForm onBack={() => setForgotMode(false)} />;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        login.mutate();
      }}
      className="mt-8 space-y-5"
    >
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jane@company.co.ke"
          autoComplete="username"
          required
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <button
            type="button"
            onClick={() => setForgotMode(true)}
            className="text-xs font-semibold text-danger hover:underline"
          >
            Forgot password?
          </button>
        </div>
        <Input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          autoComplete="current-password"
          required
        />
      </div>

      <Button
        type="submit"
        disabled={login.isPending}
        className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
      >
        {login.isPending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

function ForgotPasswordForm({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  const request = useMutation({
    mutationFn: async () =>
      api<any>("/auth/forgot-password", { method: "POST", auth: false, body: { email } }),
    onSuccess: () => setSent(true),
    onError: (err) => toast.error(describeError(err)),
  });

  if (sent) {
    return (
      <div className="mt-8 space-y-5">
        <div className="rounded-xl border border-success/30 bg-success/5 p-5">
          <div className="flex items-center gap-2 text-success">
            <Mail className="size-5" />
            <p className="text-sm font-semibold">Check your email</p>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            If <span className="font-medium text-foreground">{email}</span> is registered, a
            password reset link is on its way. It expires in 1 hour.
          </p>
        </div>
        <Button type="button" variant="outline" className="w-full" onClick={onBack}>
          Back to sign in
        </Button>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        request.mutate();
      }}
      className="mt-8 space-y-5"
    >
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reset your password</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter your account email and we'll send you a reset link.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="forgot-email">Email</Label>
        <Input
          id="forgot-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="jane@company.co.ke"
          required
        />
      </div>
      <Button
        type="submit"
        disabled={request.isPending}
        className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
      >
        {request.isPending ? "Sending…" : "Send reset link"}
      </Button>
      <button
        type="button"
        onClick={onBack}
        className="block w-full text-center text-sm font-semibold text-muted-foreground hover:text-foreground"
      >
        ← Back to sign in
      </button>
    </form>
  );
}

function SignUpForm() {
  const navigate = useNavigate();
  const [accountType, setAccountType] = useState<"personal" | "business">("personal");
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });

  const signup = useMutation({
    mutationFn: async () => {
      if (form.password.length < 8) {
        throw new Error("Password must be at least 8 characters.");
      }
      if (form.password !== form.confirm) {
        throw new Error("Passwords don't match.");
      }
      return api<any>("/auth/signup", {
        method: "POST",
        auth: false,
        body: {
          name: form.name,
          email: form.email,
          password: form.password,
          account_type: accountType,
        },
      });
    },
    onSuccess: (data) => {
      if (!data?.api_key) {
        toast.error("Account created but no session key was returned. Contact support.");
        return;
      }
      setApiKey(data.api_key);
      setOfficerName(form.name);
      toast.success("Account created — welcome to Credit Yetu");
      navigate({ to: "/dashboard" });
    },
    onError: (err) => toast.error(describeError(err)),
  });

  return (
    <form
      className="mt-8 space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        signup.mutate();
      }}
    >
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Create your account</h1>
      </div>

      <div className="space-y-2">
        <Label>Account type</Label>
        <div className="grid grid-cols-2 gap-3">
          {(
            [
              { v: "personal", label: "Individual", icon: User, hint: "Solo loan officer" },
              { v: "business", label: "Company", icon: Building2, hint: "Lending business" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.v}
              type="button"
              onClick={() => setAccountType(opt.v)}
              className={`rounded-xl border p-4 text-left transition-colors ${
                accountType === opt.v
                  ? "border-danger bg-danger/5"
                  : "border-border bg-card hover:border-muted-foreground/40"
              }`}
            >
              <opt.icon
                className={`size-5 ${accountType === opt.v ? "text-danger" : "text-muted-foreground"}`}
              />
              <p className="mt-2 text-sm font-semibold">{opt.label}</p>
              <p className="text-xs text-muted-foreground">{opt.hint}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="name">{accountType === "business" ? "Company name" : "Full name"}</Label>
        <Input
          id="name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder={accountType === "business" ? "Yetu Credit Ltd" : "Jane Wanjiru"}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Work email</Label>
        <Input
          id="email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="jane@company.co.ke"
          autoComplete="username"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          placeholder="At least 8 characters"
          autoComplete="new-password"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm">Confirm password</Label>
        <Input
          id="confirm"
          type="password"
          value={form.confirm}
          onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          placeholder="Re-enter your password"
          autoComplete="new-password"
          required
        />
      </div>

      <Button
        type="submit"
        disabled={signup.isPending}
        className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
      >
        {signup.isPending ? "Creating account…" : "Create account"}
      </Button>

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        Your password is never stored in plain text, and your data stays scoped to your organization
        only.
      </p>
    </form>
  );
}
