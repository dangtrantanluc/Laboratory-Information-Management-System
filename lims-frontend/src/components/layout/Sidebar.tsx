import { NavLink } from 'react-router-dom';
import { FlaskConical, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useAuth } from '@/context/AuthContext';
import { GROUP_LABELS, visibleNav, type NavItem } from './nav';

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onMobileClose,
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const { user } = useAuth();
  const items = visibleNav(user);
  const groups: NavItem['group'][] = ['main', 'qms', 'document', 'hr', 'research', 'catalog', 'system'];

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-blueberry/40 backdrop-blur-[2px] lg:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex flex-col border-r border-hairline bg-white transition-all duration-200',
          'lg:static lg:z-auto lg:translate-x-0',
          collapsed ? 'lg:w-[68px]' : 'lg:w-64',
          'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Brand */}
        <div
          className={cn(
            'flex h-16 shrink-0 items-center gap-2.5 border-b border-hairline px-4',
            collapsed && 'lg:justify-center lg:px-0',
          )}
        >
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blueberry text-white">
            <FlaskConical size={20} />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-bold leading-tight text-ink">LIMS</p>
              <p className="truncate text-[11px] leading-tight text-subink">Quản lý PTN</p>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
          {groups.map((group) => {
            const groupItems = items.filter((i) => i.group === group);
            if (groupItems.length === 0) return null;
            return (
              <div key={group} className="mb-5 last:mb-0">
                {!collapsed && (
                  <p className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-wider text-stem/80">
                    {GROUP_LABELS[group]}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {groupItems.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        onClick={onMobileClose}
                        title={collapsed ? item.label : undefined}
                        className={({ isActive }) =>
                          cn(
                            'group flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors',
                            collapsed && 'lg:justify-center lg:px-0',
                            isActive
                              ? 'bg-blueberry text-white'
                              : 'text-stem hover:bg-plate hover:text-ink',
                          )
                        }
                      >
                        <item.icon size={18} className="shrink-0" />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        {/* Collapse toggle (desktop) */}
        <div className="hidden shrink-0 border-t border-hairline p-3 lg:block">
          <button
            onClick={onToggle}
            className={cn(
              'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-stem hover:bg-plate hover:text-ink',
              collapsed && 'justify-center px-0',
            )}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            {!collapsed && <span>Thu gọn</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
