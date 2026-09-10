import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

interface LayoutProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

export function Layout({ title, subtitle, actions, children }: LayoutProps) {
  return (
    <div className="min-h-full">
      <Sidebar />
      <div className="pl-64">
        <Topbar title={title} subtitle={subtitle} actions={actions} />
        <main className="px-8 py-6">{children}</main>
      </div>
    </div>
  );
}
