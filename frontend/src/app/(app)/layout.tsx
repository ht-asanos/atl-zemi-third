'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { DropdownMenu, DropdownItem, DropdownSeparator } from '@/components/ui/dropdown-menu'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()
  const router = useRouter()

  const handleSignOut = async () => {
    await signOut()
    router.push('/login')
  }

  const email = user?.email || ''
  const initial = email.charAt(0).toUpperCase()

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold">自炊 x トレーニング</h2>
            <nav className="flex gap-2 text-sm">
              <Link href="/plans" className="text-muted-foreground hover:text-foreground">
                週間プラン
              </Link>
              <Link href="/daily" className="text-muted-foreground hover:text-foreground">
                Today
              </Link>
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
              <DropdownSeparator />
              <DropdownItem variant="destructive" onClick={handleSignOut}>
                ログアウト
              </DropdownItem>
            </DropdownMenu>
          )}
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}
