import { createFileRoute, Link } from "@tanstack/react-router";
import {
  BarChart3,
  FileSearch,
  Gauge,
  ScanFace,
  ShieldCheck,
  TrendingUp,
  UploadCloud,
} from "lucide-react";
import homeHero from "@/assets/home-hero.jpg";
import { Footer, TopNav } from "@/components/app-shell";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Credit Yetu · Transparent credit scoring, explained" },
      {
        name: "description",
        content:
          "Credit Yetu turns M-Pesa and bank statements into explainable credit scores, affordability ranges and verified identities for Kenyan lenders.",
      },
      { property: "og:title", content: "Credit Yetu · Transparent credit scoring, explained" },
      {
        property: "og:description",
        content:
          "Statement extraction, explainable scoring and full KYC verification in one workspace for lending teams.",
      },
    ],
  }),
  component: Home,
});

const steps = [
  {
    icon: UploadCloud,
    title: "Upload a statement",
    body: "Drop an M-Pesa, bank, till, paybill or SACCO statement as a PDF or a photo. Optical character recognition reads scanned pages too, so there is no reformatting required.",
  },
  {
    icon: FileSearch,
    title: "We extract and reconcile it",
    body: "Every transaction is parsed, classified into categories such as salary, betting, loans and remittance, and checked for gaps or tampering before a single number is calculated.",
  },
  {
    icon: Gauge,
    title: "Get a scored, explained result",
    body: "A 300 to 900 credit score, an affordability range and a grade are produced by a rule engine you can inspect line by line, with a reason attached to every flagged transaction.",
  },
  {
    icon: ScanFace,
    title: "Verify who you are lending to",
    body: "Confirm identity against IPRS, check CRB history, match a face to a national ID and look up a KRA PIN, all logged with consent so the decision holds up later.",
  },
];

const features = [
  {
    icon: Gauge,
    title: "Transparent scoring",
    body: "Every point on the 300 to 900 scale traces back to a named rule. Nothing is a black box, and nothing is left for your team to guess at.",
  },
  {
    icon: FileSearch,
    title: "Statement extraction",
    body: "M-Pesa, bank, till, paybill and SACCO statements are parsed, classified and reconciled automatically, scanned copies included.",
  },
  {
    icon: ShieldCheck,
    title: "Fraud and authenticity checks",
    body: "Self-transfers, one-off amounts outside the normal pattern and distress language are flagged automatically, each with a plain-language reason.",
  },
  {
    icon: ScanFace,
    title: "Identity verification",
    body: "IPRS lookup, face match, KRA PIN, CRB and phone checks, with the customer's consent captured on record for every check you run.",
  },
  {
    icon: TrendingUp,
    title: "Affordability and ratios",
    body: "Debt-to-income, income volatility, betting-to-income and expenses-to-income are calculated for every customer, not buried in a spreadsheet.",
  },
  {
    icon: BarChart3,
    title: "Portfolio insight",
    body: "Grade distribution, score spread and upload volume across every customer your team has scored, in one dashboard.",
  },
];

function Home() {
  return (
    <div className="min-h-screen bg-background">
      <TopNav />

      <section className="border-b border-border bg-card">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <span className="inline-flex items-center rounded-full bg-brand/15 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[color:oklch(0.55_0.12_74.5)]">
              Built for Kenyan lenders
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">
              Every credit decision,
              <br />
              explained line by line.
            </h1>
            <p className="mt-5 max-w-lg text-base text-muted-foreground">
              Most credit scores arrive as a single number with no working shown. Credit Yetu reads
              an applicant's statements, calculates a transparent score and affordability range, and
              verifies their identity against official records, so your team can see exactly why the
              number is what it is before they lend.
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
            <p className="mt-6 text-xs text-muted-foreground">
              No card required. Creating an account takes less than a minute.
            </p>
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

      <section className="border-b border-border bg-brand/5">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-bold tracking-tight">The problem with most credit scores</h2>
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
            A score with no explanation is hard to trust and impossible to appeal. Applicants get
            declined without knowing why, lenders can't defend a decision to a regulator, and every
            small mistake in a statement gets buried instead of flagged. Credit Yetu was built to
            fix that: every score, ratio and flag it produces can be traced back to a specific rule,
            on a specific transaction.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <h2 className="text-2xl font-bold tracking-tight">How it works</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          From a raw statement to a verified, explained decision in four steps.
        </p>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <div
              key={s.title}
              className="relative rounded-xl border border-border bg-card p-6 shadow-card"
            >
              <span className="text-xs font-semibold text-muted-foreground">Step {i + 1}</span>
              <span className="mt-3 grid size-10 place-items-center rounded-lg bg-brand/15 text-[color:oklch(0.55_0.12_74.5)]">
                <s.icon className="size-5" />
              </span>
              <h3 className="mt-4 text-sm font-semibold">{s.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-bold tracking-tight">What you get</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            One workspace that replaces a spreadsheet, a KYC vendor portal and a scoring black box.
          </p>
          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <div
                key={f.title}
                className="rounded-xl border border-border bg-background p-6 shadow-card"
              >
                <span className="grid size-10 place-items-center rounded-lg bg-brand/15 text-[color:oklch(0.55_0.12_74.5)]">
                  <f.icon className="size-5" />
                </span>
                <h3 className="mt-4 text-sm font-semibold">{f.title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border bg-brand/5">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-6 px-4 py-12 sm:px-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight">
              Ready to score your first customer?
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Create an account and start scoring your first customer in minutes.
            </p>
          </div>
          <Button asChild size="lg" className="bg-danger text-danger-foreground hover:bg-danger/90">
            <Link to="/login" search={{ mode: "signup" }}>
              Create account
            </Link>
          </Button>
        </div>
      </section>

      <Footer />
    </div>
  );
}
