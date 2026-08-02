import { AdminShell, type AdminView } from "@/features/admin/components/admin-shell";
import { AdminPage } from "@/features/admin/components/admin-pages";

export function AdminRoutePage({ view }: { view: AdminView }) {
  return (
    <AdminShell activeView={view}>
      <AdminPage view={view} />
    </AdminShell>
  );
}
