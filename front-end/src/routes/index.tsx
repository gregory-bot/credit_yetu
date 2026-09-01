import { createFileRoute, Link } from "@tanstack/react-router";
import { BarChart3, FileSearch, Gauge, ShieldCheck } from "lucide-react";
import homeHero from "@/assets/home-hero.jpg";
import { TopNav } from "@/components/app-shell";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Credit Yetu — Transparent credit scoring, explained" },
      {
        name: "description",
        content:
          "Credit Yetu turns M-Pesa and bank statements into explainable credit scores, affordability ranges and verified identities for Kenyan lenders.",
      },
      { property: "og:title", content: "Credit Yetu — Transparent credit scoring, explained" },
      {
        property: "og:description",
        content:
          "Statement extraction, explainable scoring and full KYC verification in one workspace for lending teams.",
      },
    ],
  }),
  component: Home,
});

const features = [
  {
    icon: Gauge,
    title: "Transparent scoring",
    body: "A 300–900 score with every reason code shown — no black box. Affordability range and grade included.",
  },
  {
    icon: FileSearch,
    title: "Statement extraction",
    body: "Drop an M-Pesa, bank, till, paybill or SACCO statement. We parse, classify and reconcile it automatically.",
  },
  {
    icon: ShieldCheck,
    title: "Identity verification",
    body: "IPRS lookup, face match, KRA PIN, CRB and phone checks — all with consent captured on record.",
  },
  {
    icon: BarChart3,
    title: "Portfolio insight",
    body: "Grade distribution, score spread and monthly upload volume across every customer you score.",
  },
];

function Home() {
  return (
    <div className="min-h-screen bg-background">
      <TopNav />

      <section className="border-b border-border bg-card">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <h1 className="mt-5 text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">
              Every credit decision,
              <br />
              explained line by line.
            </h1>
            <p className="mt-5 max-w-lg text-base text-muted-foreground">
              Credit Yetu reads your applicant's statements, scores affordability, verifies their
              identity against official records, and shows your team exactly why the number is what
              it is.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                asChild
                size="lg"
                className="bg-danger text-danger-foreground hover:bg-danger/90"
              >
                <Link to="/login" search={{ mode: "signup" }}>
                  Get started
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/dashboard">Open dashboard</Link>
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-border shadow-card">
            <img
              src={homeHero}
              alt="Small business owner using mobile money at a shop counter"
              width={1600}
              height={800}
              className="size-full object-cover"
            />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <h2 className="text-2xl font-bold tracking-tight">What you get</h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-card p-6 shadow-card">
              <span className="grid size-10 place-items-center rounded-lg bg-brand/15 text-[color:oklch(0.55_0.12_74.5)]">
                <f.icon className="size-5" />
              </span>
              <h3 className="mt-4 text-sm font-semibold">{f.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-card">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-6 px-4 py-12 sm:px-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight">
              Ready to score your first customer?
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Create an account and receive your API key instantly.
            </p>
          </div>
          <Button asChild size="lg" className="bg-danger text-danger-foreground hover:bg-danger/90">
            <Link to="/login" search={{ mode: "signup" }}>
              Create account
            </Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-border py-8 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Credit Yetu · Transparent credit scoring, explained.
      </footer>
    </div>
  );
}
