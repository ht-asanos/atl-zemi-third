'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { getMyProfile } from '@/lib/api/profiles'
import { getMyGoal } from '@/lib/api/goals'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const supabase = createClient()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (authError) {
        setError(authError.message)
        return
      }

      const token = data.session?.access_token
      if (!token) {
        setError('セッションの取得に失敗しました')
        return
      }

      // Determine redirect destination
      const profile = await getMyProfile(token)
      if (!profile) {
        router.push('/setup')
        return
      }

      const goal = await getMyGoal(token)
      if (!goal) {
        router.push('/setup')
        return
      }

      router.push('/plans')
    } catch {
      setError('ログインに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>ログイン</CardTitle>
        <CardDescription>メールアドレスとパスワードでログイン</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="email">メールアドレス</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">パスワード</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4">
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'ログイン中...' : 'ログイン'}
          </Button>
          <p className="text-sm text-muted-foreground">
            アカウントをお持ちでない方は{' '}
            <Link href="/signup" className="text-primary underline">
              サインアップ
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  )
}
