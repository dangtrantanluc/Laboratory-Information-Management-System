import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { ChevronRight, PanelLeftClose, PanelLeftOpen, X, Leaf as LeafIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useAuth } from '@/context/AuthContext';
import { useNavBadges } from '@/lib/useNavBadges';
import { useUp, useDown } from '@/lib/useMediaQuery';
import { useFocusTrap, useBodyScrollLock } from '@/lib/useFocusTrap';
import { DASHBOARD, visibleGroups, flatLeaves, type NavLeaf, type ResolvedGroup } from './nav';

function loadJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function saveJSON(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* localStorage đầy/bị chặn — bỏ qua */
  }
}

/**
 * Điều hướng chính — 3 chế độ theo bề ngang màn hình:
 *
 * | Chế độ | Điều kiện                        | Bề rộng        | Nội dung          |
 * |--------|----------------------------------|----------------|-------------------|
 * | drawer | <lg, khi người dùng mở           | 256px (overlay)| Đầy đủ            |
 * | rail   | md–lg, hoặc ≥lg khi thu gọn      | 64px (in-flow) | Icon + tooltip    |
 * | full   | ≥lg khi không thu gọn            | 208–460px      | Đầy đủ, kéo giãn  |
 *
 * Trước đây thu gọn = `lg:w-0` (biến mất hoàn toàn) và dải md–lg không có sidebar,
 * buộc người dùng iPad phải bấm hamburger cho mọi thao tác điều hướng.
 */
export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onMobileOpen,
  onMobileClose,
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileOpen: () => void;
  onMobileClose: () => void;
}) {
  const { user } = useAuth();
  const location = useLocation();
  const badges = useNavBadges();
  const uid = user?.id ?? 'anon';

  const isDesktop = useUp('lg');
  const isMobile = useDown('md');
  const isTablet = !isMobile && !isDesktop;

  // Drawer chỉ tồn tại dưới lg. Ở ≥lg người dùng đã có rail hoặc full.
  const drawerOpen = mobileOpen && !isDesktop;
  const showFull = isDesktop && !collapsed;
  const showRail = isTablet || (isDesktop && collapsed);

  const groups = useMemo(() => visibleGroups(user), [user]);
  const flat = useMemo(() => flatLeaves(user), [user]);
  const leafByPath = useMemo(() => new Map(flat.map((l) => [l.to, l])), [flat]);

  // Mục "active" = item có đường dẫn khớp DÀI NHẤT với URL hiện tại.
  // Nhờ vậy ở /documents/pending chỉ "Chờ duyệt" sáng (không kéo theo "Tài liệu"),
  // còn ở /documents/:id (trang chi tiết) thì "Tài liệu" vẫn sáng đúng.
  const activePath = useMemo(() => {
    const path = location.pathname;
    let best = '';
    for (const l of flat) {
      if ((path === l.to || path.startsWith(l.to + '/')) && l.to.length > best.length) best = l.to;
    }
    return best;
  }, [flat, location.pathname]);

  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);

  // ── Drawer: khoá cuộn nền, giam focus, đóng bằng Esc ──
  const drawerRef = useRef<HTMLElement>(null);
  useBodyScrollLock(drawerOpen);
  useFocusTrap(drawerRef, drawerOpen);
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onMobileClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawerOpen, onMobileClose]);

  // Drawer đóng vẫn nằm trong DOM (để có animation) → phải chặn Tab lọt vào.
  // `inert` chưa có trong kiểu của React 18 nên gán qua DOM.
  useEffect(() => {
    const el = drawerRef.current as (HTMLElement & { inert?: boolean }) | null;
    if (el) el.inert = !drawerOpen;
  }, [drawerOpen, isDesktop]);

  // Kéo dãn độ rộng sidebar (chỉ chế độ full) — lưu lại giữa các phiên
  const WIDTH_KEY = 'lims_sidebar_width';
  const MIN_W = 208;
  const MAX_W = 460;
  const [width, setWidth] = useState<number>(() => {
    const v = loadJSON<number>(WIDTH_KEY, 256);
    return Math.min(MAX_W, Math.max(MIN_W, v));
  });
  const [isDragging, setIsDragging] = useState(false);
  const draggingRef = useRef(false);
  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!draggingRef.current) return;
      setWidth(Math.min(MAX_W, Math.max(MIN_W, e.clientX)));
    }
    function onUp() {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setWidth((w) => {
        saveJSON(WIDTH_KEY, w);
        return w;
      });
    }
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, []);
  function startDrag(e: React.PointerEvent) {
    e.preventDefault();
    draggingRef.current = true;
    setIsDragging(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }

  // Favorites (ghim) — theo user
  const favKey = `lims_nav_favorites:${uid}`;
  const [favorites, setFavorites] = useState<string[]>(() => loadJSON(favKey, []));
  function toggleFavorite(to: string) {
    setFavorites((prev) => {
      const next = prev.includes(to) ? prev.filter((p) => p !== to) : [...prev, to];
      saveJSON(favKey, next);
      return next;
    });
  }

  // Recent (vừa truy cập) — theo user, tối đa 5
  const recentKey = `lims_nav_recent:${uid}`;
  const [recent, setRecent] = useState<string[]>(() => loadJSON(recentKey, []));
  useEffect(() => {
    if (!leafByPath.has(location.pathname)) return;
    setRecent((prev) => {
      const next = [location.pathname, ...prev.filter((p) => p !== location.pathname)].slice(0, 5);
      saveJSON(recentKey, next);
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Trạng thái gập/mở của nhóm — theo user (nhớ giữa các phiên)
  const openKey = `lims_nav_groups:${uid}`;
  const [open, setOpen] = useState<Record<string, boolean>>(() => {
    const saved = loadJSON<Record<string, boolean> | null>(openKey, null);
    if (saved) return saved;
    return Object.fromEntries(groups.map((g) => [g.id, !!g.defaultOpen]));
  });
  function toggleGroup(id: string) {
    setOpen((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      saveJSON(openKey, next);
      return next;
    });
  }

  // Nhóm chứa trang đang đứng → tự mở để luôn thấy vị trí hiện tại.
  const activeGroupId = useMemo(() => {
    for (const g of groups) {
      const hit =
        g.items.some((l) => l.to === location.pathname) ||
        g.subgroups.some((sg) => sg.items.some((l) => l.to === location.pathname));
      if (hit) return g.id;
    }
    return null;
  }, [groups, location.pathname]);
  useEffect(() => {
    if (!activeGroupId) return;
    setOpen((prev) => {
      if (prev[activeGroupId]) return prev;
      const next = { ...prev, [activeGroupId]: true };
      saveJSON(openKey, next);
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGroupId]);

  const q = query.trim().toLowerCase();
  const searchResults = q ? flat.filter((l) => l.label.toLowerCase().includes(q)) : [];

  const favLeaves = favorites.map((to) => leafByPath.get(to)).filter(Boolean) as NavLeaf[];
  // Gần đây → chỉ hiện trong dropdown ô Tìm; bỏ trang hiện tại + mục đã ghim.
  const recentLeaves = recent
    .filter((to) => !favorites.includes(to) && to !== location.pathname)
    .map((to) => leafByPath.get(to))
    .filter(Boolean) as NavLeaf[];

  // Tổng badge của 1 nhóm (để hiện chấm khi nhóm đang đóng)
  function groupBadgeTotal(g: ResolvedGroup): number {
    const all = [...g.items, ...g.subgroups.flatMap((s) => s.items)];
    return all.reduce((sum, l) => sum + (l.badge ? badges[l.badge] ?? 0 : 0), 0);
  }

  const leafCount = (l: NavLeaf) => (l.badge ? badges[l.badge] : undefined);

  /** Thanh thương hiệu — ở rail chỉ còn logo căn giữa. */
  function renderBrand(rail: boolean) {
    return (
      <div
        className={cn(
          'relative flex h-[72px] shrink-0 items-center overflow-hidden bg-blueberry shadow-md',
          rail ? 'justify-center px-2' : 'justify-between px-4',
        )}
      >
        <LeafIcon
          aria-hidden
          className="pointer-events-none absolute -right-3 -top-3 h-20 w-20 rotate-12 text-white/10"
          strokeWidth={0.8}
        />
        {rail ? (
          <img
            src="/ribe-logo.jpeg"
            alt="RIBE"
            title="Viện Sinh học — Quản lý phòng thí nghiệm"
            className="relative h-9 w-9 shrink-0 rounded-full bg-white object-contain ring-1 ring-white/60"
          />
        ) : (
          <>
            <div className="relative flex min-w-0 items-center gap-2.5">
              <img
                src="/ribe-logo.jpeg"
                alt="RIBE"
                className="h-8 w-8 shrink-0 rounded-full bg-white object-contain ring-1 ring-white/60"
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-bold leading-tight text-white">Viện Sinh học</p>
                <p className="truncate text-[11px] leading-tight text-white/70">
                  Quản lý phòng thí nghiệm
                </p>
              </div>
            </div>
            {isDesktop ? (
              <button
                onClick={onToggle}
                title="Thu gọn menu"
                aria-label="Thu gọn menu"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white/80 transition-all duration-150 hover:bg-white/15 hover:text-white active:scale-90"
              >
                <PanelLeftClose size={18} />
              </button>
            ) : (
              // Dưới lg nội dung này nằm trong drawer → cần nút đóng tường minh,
              // không chỉ dựa vào chạm nền (người dùng cảm ứng hay bỏ sót).
              <button
                onClick={onMobileClose}
                title="Đóng menu"
                aria-label="Đóng menu"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-white/80 transition-all duration-150 hover:bg-white/15 hover:text-white active:scale-90"
              >
                <X size={20} />
              </button>
            )}
          </>
        )}
      </div>
    );
  }

  /** Nội dung đầy đủ — dùng cho drawer (<lg) và chế độ full (≥lg). */
  function renderFullContent() {
    return (
      <>
        {renderBrand(false)}

        {/* Ô tìm kiếm trong menu (kèm gợi ý "Gần đây" khi focus) */}
        <div className="relative z-20 shrink-0 px-3 pt-3">
          <div className="relative">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
              placeholder="Tìm chức năng…"
              type="text"
              name="lims-menu-filter"
              aria-label="Tìm chức năng trong menu"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              aria-autocomplete="none"
              data-lpignore="true"
              data-1p-ignore
              data-form-type="other"
              className="h-9 w-full rounded-lg border border-hairline bg-plate px-3 pr-7 text-sm text-ink placeholder:text-stem/70 focus:border-blueberry/40 focus:bg-surface focus:outline-none focus:ring-2 focus:ring-blueberry/20"
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                title="Xóa"
                aria-label="Xoá từ khoá tìm"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-stem hover:text-ink"
              >
                ✕
              </button>
            )}
          </div>

          {/* Dropdown "Gần đây" — hiện khi bấm vào ô tìm và chưa gõ gì */}
          {searchFocused && !q && recentLeaves.length > 0 && (
            <div className="absolute inset-x-3 top-full mt-1 rounded-lg border border-hairline bg-surface p-1 shadow-lg">
              <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-ink/60">
                Gần đây
              </p>
              <ul className="space-y-0.5">
                {recentLeaves.map((l) => {
                  const Icon = l.icon;
                  return (
                    <li key={l.to}>
                      <button
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => {
                          navigate(l.to);
                          setSearchFocused(false);
                          onMobileClose();
                        }}
                        className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-sm font-medium text-stem transition-all duration-150 hover:translate-x-0.5 hover:bg-blueberry/10 hover:text-blueberry"
                      >
                        {Icon ? <Icon size={16} className="shrink-0" /> : <span className="w-4" />}
                        <span className="flex-1 truncate">{l.label}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-3 scrollbar-thin">
          {q ? (
            // ── Kết quả tìm kiếm ──
            <div>
              <SectionLabel>Kết quả ({searchResults.length})</SectionLabel>
              {searchResults.length === 0 ? (
                <p className="px-2.5 py-2 text-sm text-subink">Không có chức năng phù hợp.</p>
              ) : (
                <ul className="space-y-0.5">
                  {searchResults.map((l) => (
                    <Leaf
                      key={l.to}
                      leaf={l}
                      count={leafCount(l)}
                      isFav={favorites.includes(l.to)}
                      active={l.to === activePath}
                      onToggleFav={toggleFavorite}
                      onNavigate={onMobileClose}
                    />
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <>
              {/* Tổng quan (Home) — luôn trên cùng */}
              <ul className="space-y-0.5">
                <Leaf
                  leaf={DASHBOARD}
                  isFav={favorites.includes(DASHBOARD.to)}
                  active={DASHBOARD.to === activePath}
                  onToggleFav={toggleFavorite}
                  onNavigate={onMobileClose}
                />
              </ul>

              {/* Favorites */}
              {favLeaves.length > 0 && (
                <div className="mt-4 border-t border-hairline pt-3">
                  <SectionLabel>Ghim</SectionLabel>
                  <ul className="space-y-0.5">
                    {favLeaves.map((l) => (
                      <Leaf
                        key={l.to}
                        leaf={l}
                        count={leafCount(l)}
                        isFav
                        active={l.to === activePath}
                        onToggleFav={toggleFavorite}
                        onNavigate={onMobileClose}
                      />
                    ))}
                  </ul>
                </div>
              )}

              {/* Nhóm gập/mở — giãn cách rõ giữa các nhóm + đường guide dọc cho mục con */}
              <div className="mt-5 space-y-3 border-t border-hairline pt-4">
                {groups.map((g) => {
                  const isOpen = open[g.id] ?? !!g.defaultOpen;
                  const total = groupBadgeTotal(g);
                  return (
                    <div key={g.id}>
                      <button
                        onClick={() => toggleGroup(g.id)}
                        aria-expanded={isOpen}
                        className="flex w-full items-center gap-1.5 rounded-md py-1.5 pl-2 pr-2 text-[11px] font-bold uppercase tracking-wider text-ink/75 transition-colors duration-150 hover:bg-blueberry/10 hover:text-blueberry"
                      >
                        <ChevronRight
                          size={12}
                          className={cn(
                            'shrink-0 text-stem transition-transform duration-200',
                            isOpen && 'rotate-90',
                          )}
                        />
                        <span className="flex-1 text-left">{g.label}</span>
                        {!isOpen && total > 0 && (
                          <span
                            className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-berry"
                            title={`${total} mục cần xử lý`}
                          />
                        )}
                      </button>
                      <div
                        className={cn(
                          'grid transition-[grid-template-rows,opacity] duration-200 ease-out',
                          isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
                        )}
                      >
                        <div className="overflow-hidden">
                          <div className="ml-4 mt-1.5 space-y-0.5 border-l border-hairline pl-2">
                            {/* items phẳng */}
                            {g.items.length > 0 && (
                              <ul className="space-y-0.5">
                                {g.items.map((l) => (
                                  <Leaf
                                    key={l.to}
                                    leaf={l}
                                    count={leafCount(l)}
                                    isFav={favorites.includes(l.to)}
                                    active={l.to === activePath}
                                    onToggleFav={toggleFavorite}
                                    onNavigate={onMobileClose}
                                    indent="pl-1.5"
                                  />
                                ))}
                              </ul>
                            )}
                            {/* nhóm con — thụt sâu thêm một cấp */}
                            {g.subgroups.map((sg) => (
                              <div key={sg.label} className="pt-2">
                                <p className="mb-1 pl-1.5 pr-2 text-[10px] font-semibold uppercase tracking-wide text-subink">
                                  {sg.label}
                                </p>
                                <ul className="space-y-0.5">
                                  {sg.items.map((l) => (
                                    <Leaf
                                      key={l.to}
                                      leaf={l}
                                      count={leafCount(l)}
                                      isFav={favorites.includes(l.to)}
                                      active={l.to === activePath}
                                      onToggleFav={toggleFavorite}
                                      onNavigate={onMobileClose}
                                      indent="pl-4"
                                    />
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </nav>
      </>
    );
  }

  /** Nội dung rail — icon + tooltip, giữ ranh giới nhóm bằng đường kẻ mảnh. */
  function renderRailContent() {
    return (
      <>
        {renderBrand(true)}

        {/* Nút mở rộng: ở desktop → bung full; ở tablet → mở drawer đầy đủ */}
        <div className="shrink-0 border-b border-hairline px-2 py-2">
          <button
            onClick={isDesktop ? onToggle : onMobileOpen}
            title={isDesktop ? 'Mở rộng menu' : 'Mở menu đầy đủ'}
            aria-label={isDesktop ? 'Mở rộng menu' : 'Mở menu đầy đủ'}
            className="flex h-9 w-full items-center justify-center rounded-lg text-stem transition-colors hover:bg-blueberry/10 hover:text-blueberry"
          >
            <PanelLeftOpen size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-2 scrollbar-thin" aria-label="Điều hướng thu gọn">
          <ul className="space-y-0.5">
            <RailLeaf leaf={DASHBOARD} active={DASHBOARD.to === activePath} />
          </ul>

          {favLeaves.length > 0 && (
            <ul className="mt-2 space-y-0.5 border-t border-hairline pt-2">
              {favLeaves.map((l) => (
                <RailLeaf key={l.to} leaf={l} count={leafCount(l)} active={l.to === activePath} />
              ))}
            </ul>
          )}

          {groups.map((g) => {
            const items = [...g.items, ...g.subgroups.flatMap((sg) => sg.items)];
            if (items.length === 0) return null;
            return (
              <ul key={g.id} className="mt-2 space-y-0.5 border-t border-hairline pt-2">
                {items.map((l) => (
                  <RailLeaf key={l.to} leaf={l} count={leafCount(l)} active={l.to === activePath} />
                ))}
              </ul>
            );
          })}
        </nav>
      </>
    );
  }

  return (
    <>
      {/* Overlay drawer — chỉ dưới lg */}
      {drawerOpen && (
        <div
          aria-hidden
          className="fixed inset-0 z-40 bg-blueberry/40 backdrop-blur-[2px] lg:hidden"
          onClick={onMobileClose}
        />
      )}

      {/* ── IN-FLOW: rail (md–lg, hoặc ≥lg khi thu gọn) / full (≥lg) ── */}
      {!isMobile && (
        <aside
          style={showFull ? { width } : undefined}
          className={cn(
            'relative flex shrink-0 flex-col border-r border-hairline bg-surface',
            isDragging ? 'transition-none' : 'transition-all duration-200',
            showRail && 'w-16',
          )}
        >
          {showFull ? renderFullContent() : renderRailContent()}

          {/* Thanh kéo dãn độ rộng — chỉ ở chế độ full */}
          {showFull && (
            <div
              onPointerDown={startDrag}
              onDoubleClick={() => {
                setWidth(256);
                saveJSON(WIDTH_KEY, 256);
              }}
              title="Kéo để đổi độ rộng · nháy đúp để đặt lại"
              className="group absolute inset-y-0 -right-1 z-50 w-2 cursor-col-resize touch-none"
            >
              <div
                className={cn(
                  'ml-auto h-full w-px transition-colors',
                  isDragging
                    ? 'w-0.5 bg-blueberry/60'
                    : 'bg-transparent group-hover:w-0.5 group-hover:bg-blueberry/40',
                )}
              />
            </div>
          )}
        </aside>
      )}

      {/* ── DRAWER: overlay đầy đủ, chỉ dưới lg ── */}
      {!isDesktop && (
        <aside
          ref={drawerRef}
          aria-hidden={!drawerOpen}
          className={cn(
            'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-hairline bg-surface transition-transform duration-200',
            drawerOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          {renderFullContent()}
        </aside>
      )}
    </>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1 pl-7 pr-2 text-[10px] font-bold uppercase tracking-wide text-ink/70">
      {children}
    </p>
  );
}

/** Mục điều hướng ở chế độ rail — chỉ icon, badge thu thành chấm. */
function RailLeaf({ leaf, count, active }: { leaf: NavLeaf; count?: number; active: boolean }) {
  const Icon = leaf.icon;
  return (
    <li>
      <NavLink
        to={leaf.to}
        title={leaf.label}
        aria-label={leaf.label}
        className={cn(
          'relative flex h-10 items-center justify-center rounded-lg transition-colors duration-150',
          active
            ? 'bg-gradient-to-r from-blueberry to-berry text-white shadow-sm'
            : 'text-stem hover:bg-blueberry/10 hover:text-blueberry',
        )}
      >
        {Icon ? <Icon size={19} /> : <span className="h-5 w-5" />}
        {count && count > 0 ? (
          <span
            className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-berry ring-2 ring-surface"
            title={`${count} mục cần xử lý`}
          />
        ) : null}
      </NavLink>
    </li>
  );
}

function Leaf({
  leaf,
  count,
  isFav,
  active,
  onToggleFav,
  onNavigate,
  indent = 'pl-2.5',
}: {
  leaf: NavLeaf;
  count?: number;
  isFav: boolean;
  /** Sáng khi item khớp URL (theo prefix dài nhất — tính ở component cha). */
  active: boolean;
  onToggleFav: (to: string) => void;
  onNavigate: () => void;
  /** Lề trái: mặc định icon sát trái; nhóm con thụt sâu hơn một cấp. */
  indent?: string;
}) {
  const Icon = leaf.icon;

  return (
    <li>
      <NavLink
        to={leaf.to}
        onClick={onNavigate}
        className={cn(
          'group relative flex items-center gap-2.5 overflow-hidden rounded-lg py-2 pr-2 text-sm font-medium transition-all duration-150 ease-out',
          indent,
          active
            ? 'bg-gradient-to-r from-blueberry to-berry text-white shadow-sm'
            : 'text-stem hover:translate-x-0.5 hover:bg-blueberry/10 hover:text-blueberry',
        )}
      >
        {/* Thanh chỉ báo bên trái — trượt vào khi active/hover */}
        <span
          className={cn(
            'absolute inset-y-1 left-0 w-[3px] rounded-r bg-white transition-transform duration-200 ease-out',
            active ? 'translate-x-0' : '-translate-x-full bg-blueberry group-hover:translate-x-0',
          )}
        />
        {Icon ? (
          <span className="flex h-5 w-5 shrink-0 items-center justify-center text-current transition-transform duration-150 group-hover:scale-110">
            <Icon size={18} />
          </span>
        ) : (
          <span className="w-5" />
        )}
        <span className="flex-1 truncate">{leaf.label}</span>
        {count && count > 0 ? (
          <span
            className={cn(
              'min-w-[18px] rounded-full px-1.5 text-center text-[11px] font-semibold leading-[18px] transition-colors',
              active ? 'bg-white/25 text-white' : 'bg-berry text-white',
            )}
          >
            {count > 99 ? '99+' : count}
          </span>
        ) : null}
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleFav(leaf.to);
          }}
          title={isFav ? 'Bỏ ghim' : 'Ghim'}
          aria-label={isFav ? `Bỏ ghim ${leaf.label}` : `Ghim ${leaf.label}`}
          // -m-1 p-1: mở rộng vùng chạm ~14px → ~26px mà không đẩy layout.
          // touch-visible: trên thiết bị không hover, nút ẩn sẽ không bao giờ hiện được.
          className={cn(
            '-m-1 shrink-0 p-1 text-sm leading-none transition-all duration-150 hover:scale-125',
            isFav
              ? cn('opacity-100', active ? 'text-white' : 'text-warning')
              : cn(
                  'touch-visible opacity-0 group-hover:opacity-100',
                  active ? 'text-white/70 hover:text-white' : 'text-stem hover:text-ink',
                ),
          )}
        >
          {isFav ? '★' : '☆'}
        </button>
      </NavLink>
    </li>
  );
}
