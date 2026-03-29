'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { DropdownMenu, DropdownItem, DropdownSeparator } from '@/components/ui/dropdown-menu'
import { BottomNav } from '@/components/ui/bottom-nav'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isAdmin, signOut } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  const handleSignOut = async () => {
    await signOut()
    router.push('/login')
  }

  const email = user?.email || ''
  const initial = email.charAt(0).toUpperCase()

  const isActive = (path: string) => pathname.startsWith(path)

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold">自炊 x トレーニング</h2>
            <nav className="hidden sm:flex gap-2 text-sm">
              <Link
                href="/plans"
                aria-current={isActive('/plans') ? 'page' : undefined}
                className={`pb-0.5 transition-colors ${isActive('/plans') ? 'text-foreground font-medium border-b-2 border-foreground' : 'text-muted-foreground hover:text-foreground'}`}
              >
                週間プラン
              </Link>
              <Link
                href="/daily"
                aria-current={isActive('/daily') ? 'page' : undefined}
                className={`pb-0.5 transition-colors ${isActive('/daily') ? 'text-foreground font-medium border-b-2 border-foreground' : 'text-muted-foreground hover:text-foreground'}`}
              >
                Today
              </Link>
              {isAdmin ? (
                <Link
                  href="/admin/training-progressions"
                  aria-current={isActive('/admin') ? 'page' : undefined}
                  className={`pb-0.5 transition-colors ${isActive('/admin') ? 'text-foreground font-medium border-b-2 border-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  管理
                </Link>
              ) : null}
            </nav>
          </div>
          {user && (
            <DropdownMenu
              trigger={
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-medium">
                  {initial}
                </div>
              }
            >
              <DropdownItem disabled>{email}</DropdownItem>
              <DropdownSeparator />
              <DropdownItem onClick={() => router.push('/settings/profile')}>
                プロフィール編集
              </DropdownItem>
              <DropdownItem onClick={() => router.push('/settings/goal')}>
                目標変更
              </DropdownItem>
              <DropdownItem onClick={() => router.push('/staple?from=settings')}>
                プラン生成設定
              </DropdownItem>
              {isAdmin ? (
                <DropdownItem onClick={() => router.push('/admin/training-progressions')}>
                  管理画面
                </DropdownItem>
              ) : null}
              <DropdownSeparator />
              <DropdownItem variant="destructive" onClick={handleSignOut}>
                ログアウト
              </DropdownItem>
            </DropdownMenu>
          )}
        </div>
      </header>
      <main className="pb-16 sm:pb-0">{children}</main>
      <BottomNav isAdmin={!!isAdmin} onSignOut={handleSignOut} />
    </div>
  )
}
