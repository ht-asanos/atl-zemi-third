'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { CalendarDays, Sun, Menu, X, Settings, LogOut, Target, ChevronRight } from 'lucide-react'
import { useState } from 'react'

interface BottomNavProps {
  isAdmin: boolean
  onSignOut: () => void
}

export function BottomNav({ isAdmin, onSignOut }: BottomNavProps) {
  const pathname = usePathname()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)

  const isActive = (path: string) => pathname.startsWith(path)

  return (
    <>
      {/* ボトムナビゲーションバー (sm未満のみ表示) */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center border-t border-border bg-background sm:hidden">
        <Link
          href="/plans"
          className="flex flex-1 flex-col items-center justify-center gap-1 py-2 transition-colors"
          style={{ color: isActive('/plans') ? 'var(--primary)' : 'var(--muted-foreground)' }}
          aria-current={isActive('/plans') ? 'page' : undefined}
        >
          <CalendarDays size={20} />
          <span className="text-[10px] font-medium">プラン</span>
        </Link>
        <Link
          href="/daily"
          className="flex flex-1 flex-col items-center justify-center gap-1 py-2 transition-colors"
          style={{ color: isActive('/daily') ? 'var(--primary)' : 'var(--muted-foreground)' }}
          aria-current={isActive('/daily') ? 'page' : undefined}
        >
          <Sun size={20} />
          <span className="text-[10px] font-medium">Today</span>
        </Link>
        <button
          type="button"
          onClick={() => setMenuOpen(true)}
          className="flex flex-1 flex-col items-center justify-center gap-1 py-2 transition-colors"
          style={{ color: menuOpen ? 'var(--primary)' : 'var(--muted-foreground)' }}
          aria-label="メニューを開く"
        >
          <Menu size={20} />
          <span className="text-[10px] font-medium">メニュー</span>
        </button>
      </nav>

      {/* メニューボトムシート */}
      {menuOpen && (
        <>
          {/* バックドロップ */}
          <div
            className="fixed inset-0 z-50 bg-black/40 sm:hidden animate-fade-in"
            onClick={() => setMenuOpen(false)}
          />
          {/* シート本体 */}
          <div className="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl bg-background pb-safe sm:hidden animate-slide-up">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <span className="text-sm font-medium text-foreground">メニュー</span>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground"
                aria-label="閉じる"
              >
                <X size={16} />
              </button>
            </div>
            <div className="px-4 py-2">
              <MenuSheetItem
                icon={<Settings size={16} />}
                label="プロフィール編集"
                onClick={() => { router.push('/settings/profile'); setMenuOpen(false) }}
              />
              <MenuSheetItem
                icon={<Target size={16} />}
                label="目標変更"
                onClick={() => { router.push('/settings/goal'); setMenuOpen(false) }}
              />
              <MenuSheetItem
                icon={<CalendarDays size={16} />}
                label="プラン生成設定"
                onClick={() => { router.push('/staple?from=settings'); setMenuOpen(false) }}
              />
              {isAdmin && (
                <MenuSheetItem
                  icon={<Settings size={16} />}
                  label="管理画面"
                  onClick={() => { router.push('/admin/training-progressions'); setMenuOpen(false) }}
                />
              )}
              <div className="my-2 border-t border-border" />
              <button
                type="button"
                onClick={() => { onSignOut(); setMenuOpen(false) }}
                className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left text-sm text-destructive transition-colors hover:bg-muted"
              >
                <LogOut size={16} />
                <span>ログアウト</span>
              </button>
            </div>
            {/* iOS safe area */}
            <div className="h-6" />
          </div>
        </>
      )}
    </>
  )
}

function MenuSheetItem({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-sm text-foreground transition-colors hover:bg-muted"
    >
      <div className="flex items-center gap-3 text-muted-foreground">
        {icon}
        <span className="text-foreground">{label}</span>
      </div>
      <ChevronRight size={14} className="text-muted-foreground" />
    </button>
  )
}
