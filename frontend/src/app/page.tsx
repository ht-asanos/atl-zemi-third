'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/providers/auth-provider'
import { getMyProfile } from '@/lib/api/profiles'
import { getMyGoal } from '@/lib/api/goals'

export default function Home() {
  const { session, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return

    if (!session) {
      router.push('/login')
      return
    }

    const token = session.access_token
    ;(async () => {
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
    })()
  }, [session, isLoading, router])

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">リダイレクト中...</p>
    </div>
  )
}
