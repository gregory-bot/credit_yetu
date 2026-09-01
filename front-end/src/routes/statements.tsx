import { createFileRoute, Outlet } from "@tanstack/react-router";

// A pure layout route: TanStack Router nests /statements/$referenceId under
// this because both files start with "statements." — without rendering an
// <Outlet/> here, the child route's URL changes but its content has nowhere
// to appear (exactly the "View does nothing" bug this file exists to fix).
// The actual list page now lives in statements.index.tsx.
export const Route = createFileRoute("/statements")({
  component: () => <Outlet />,
});
