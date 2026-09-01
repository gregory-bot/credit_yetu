import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Building2, Plus, Search, User } from "lucide-react";
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
import { EmptyState, ErrorNote, SectionCard } from "@/components/ui-bits";
import { api, describeError } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";

export const Route = createFileRoute("/customers")({
  head: () => ({
    meta: [
      { title: "Customers — Credit Yetu" },
      {
        name: "description",
        content: "Every individual and company customer your team has registered.",
      },
    ],
  }),
  component: CustomersPage,
});

type Customer = {
  uuid: string;
  full_name: string;
  national_id: string;
  phone: string | null;
  gender: string | null;
  location: string | null;
  email: string | null;
  entity_type: "individual" | "business";
  business_name: string | null;
  business_reg_no: string | null;
};

function CustomersPage() {
  const { ready, isAuthenticated } = useRequireAuth();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const customers = useQuery({
    queryKey: ["customers"],
    enabled: ready && isAuthenticated,
    queryFn: () => api<Customer[]>("/customers"),
  });

  const rows = useMemo(() => customers.data ?? [], [customers.data]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((c) =>
      [c.full_name, c.national_id, c.phone, c.business_name, c.email]
        .filter(Boolean)
        .some((v) => v!.toLowerCase().includes(q)),
    );
  }, [rows, search]);

  if (!ready || !isAuthenticated) return null;

  return (
    <AppPage
      title="Customers"
      description="Individual and company profiles your team has registered."
      actions={
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-danger text-danger-foreground hover:bg-danger/90">
              <Plus className="size-4" /> New customer
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>New customer</DialogTitle>
            </DialogHeader>
            <NewCustomerForm onDone={() => setOpen(false)} />
          </DialogContent>
        </Dialog>
      }
    >
      <div className="space-y-6">
        {customers.isError && <ErrorNote message={describeError(customers.error)} />}

        <div className="relative max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, national ID, phone…"
            className="pl-9"
          />
        </div>

        <SectionCard title={`${filtered.length} customer${filtered.length === 1 ? "" : "s"}`}>
          {filtered.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-brand/15 text-left text-xs uppercase tracking-wide">
                    <th className="rounded-l-md px-3 py-2 font-semibold">Name</th>
                    <th className="px-3 py-2 font-semibold">National ID</th>
                    <th className="px-3 py-2 font-semibold">Type</th>
                    <th className="px-3 py-2 font-semibold">Phone</th>
                    <th className="rounded-r-md px-3 py-2 font-semibold" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.uuid} className="border-b border-border last:border-0">
                      <td className="px-3 py-2.5 font-medium">
                        <span className="inline-flex items-center gap-2">
                          {c.entity_type === "business" ? (
                            <Building2 className="size-3.5 text-muted-foreground" />
                          ) : (
                            <User className="size-3.5 text-muted-foreground" />
                          )}
                          {c.business_name || c.full_name}
                        </span>
                      </td>
                      <td className="num px-3 py-2.5 text-xs">{c.national_id}</td>
                      <td className="px-3 py-2.5 capitalize text-muted-foreground">
                        {c.entity_type}
                      </td>
                      <td className="num px-3 py-2.5 text-xs text-muted-foreground">
                        {c.phone ?? "—"}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <Button asChild size="sm" variant="ghost">
                          <Link to="/statements" search={{ national_id: c.national_id }}>
                            View statements
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
              title={search ? "No matches" : "No customers yet"}
              description={
                search
                  ? "Try a different search term."
                  : "Add your first customer to start building a portfolio."
              }
            />
          )}
        </SectionCard>
      </div>
    </AppPage>
  );
}

function NewCustomerForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const [entityType, setEntityType] = useState<"individual" | "business">("individual");
  const [form, setForm] = useState({
    full_name: "",
    national_id: "",
    phone: "",
    gender: "",
    location: "",
    email: "",
    business_name: "",
    business_reg_no: "",
    tax_id: "",
  });

  const create = useMutation({
    mutationFn: () =>
      api("/customers", {
        method: "POST",
        body: {
          ...form,
          entity_type: entityType,
          gender: form.gender || undefined,
          phone: form.phone || undefined,
          location: form.location || undefined,
          email: form.email || undefined,
          business_name: entityType === "business" ? form.business_name || undefined : undefined,
          business_reg_no:
            entityType === "business" ? form.business_reg_no || undefined : undefined,
          tax_id: entityType === "business" ? form.tax_id || undefined : undefined,
        },
      }),
    onSuccess: () => {
      toast.success("Customer registered");
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      onDone();
    },
    onError: (err) => toast.error(describeError(err)),
  });

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        {(["individual", "business"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setEntityType(t)}
            className={`rounded-xl border p-3 text-left text-sm font-semibold capitalize transition-colors ${
              entityType === t
                ? "border-danger bg-danger/5"
                : "border-border hover:border-muted-foreground/40"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <Label htmlFor="full_name">
          {entityType === "business" ? "Contact person's full name" : "Full name"}
        </Label>
        <Input
          id="full_name"
          required
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
      </div>

      {entityType === "business" && (
        <>
          <div className="space-y-2">
            <Label htmlFor="business_name">Business name</Label>
            <Input
              id="business_name"
              value={form.business_name}
              onChange={(e) => setForm({ ...form, business_name: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="business_reg_no">Registration no.</Label>
              <Input
                id="business_reg_no"
                value={form.business_reg_no}
                onChange={(e) => setForm({ ...form, business_reg_no: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tax_id">KRA PIN</Label>
              <Input
                id="tax_id"
                value={form.tax_id}
                onChange={(e) => setForm({ ...form, tax_id: e.target.value })}
              />
            </div>
          </div>
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="national_id">National ID</Label>
          <Input
            id="national_id"
            required
            value={form.national_id}
            onChange={(e) => setForm({ ...form, national_id: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="phone">Phone</Label>
          <Input
            id="phone"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="2547XXXXXXXX"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>Gender</Label>
          <Select value={form.gender} onValueChange={(v) => setForm({ ...form, gender: v })}>
            <SelectTrigger>
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="M">Male</SelectItem>
              <SelectItem value="F">Female</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="location">Location</Label>
          <Input
            id="location"
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder="Nairobi"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
      </div>

      <Button
        type="submit"
        disabled={create.isPending}
        className="w-full bg-danger text-danger-foreground hover:bg-danger/90"
      >
        {create.isPending ? "Saving…" : "Register customer"}
      </Button>
    </form>
  );
}
