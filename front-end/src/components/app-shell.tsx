import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut, Menu } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { clearApiKey } from "@/lib/api";
import { useApiKey } from "@/lib/auth";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="leading-tight">
        <span className="block text-base font-bold tracking-tight text-brand-foreground">
          Credit Yetu
        </span>
        <span className={`block text-[11px] ${light ? "text-brand-foreground/70" : "text-muted-foreground"}`}>
          Transparent credit scoring, explained.
        </span>
      </span>
    </Link>
  );
}

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/customers", label: "Customers" },
  { to: "/statements", label: "Statements" },
  { to: "/verify", label: "Verify" },
  { to: "/settings", label: "Settings" },
] as const;

export function TopNav() {
  const { isAuthenticated } = useApiKey();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-brand">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6">
        <Logo light />
        <nav className="ml-auto hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="rounded-md px-3 py-2 text-sm font-medium text-brand-foreground/85 transition-colors hover:bg-brand-foreground/10 hover:text-brand-foreground"
              activeProps={{ className: "bg-brand-foreground/15 text-brand-foreground" }}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 md:ml-0">
          {isAuthenticated ? (
            <Button
              size="sm"
              variant="ghost"
              className="text-brand-foreground hover:bg-brand-foreground/10"
              onClick={() => {
                clearApiKey();
                navigate({ to: "/login", search: { mode: "signin" } });
              }}
            >
              <LogOut className="size-4" /> Sign out
            </Button>
          ) : (
            <Button asChild size="sm" className="bg-danger text-danger-foreground hover:bg-danger/90">
              <Link to="/login" search={{ mode: "signin" }}>
                Sign in
              </Link>
            </Button>
          )}
          <button
            className="rounded-md p-2 text-brand-foreground md:hidden"
            onClick={() => setOpen((o) => !o)}
            aria-label="Toggle navigation"
          >
            <Menu className="size-5" />
          </button>
        </div>
      </div>
      {open && (
        <nav className="border-t border-brand-foreground/15 px-4 pb-3 md:hidden">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className="block rounded-md px-3 py-2 text-sm font-medium text-brand-foreground/90"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

export function AppPage({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
            {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
          </div>
          {actions}
        </div>
        {children}
      </main>
    </div>
  );
}
