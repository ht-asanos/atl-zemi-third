'use client'

import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { getMyAdminStatus } from '@/lib/api/profiles'
import { createClient } from '@/lib/supabase/client'
import type { Session, User } from '@supabase/supabase-js'

interface AuthContextType {
  session: Session | null
  user: User | null
  isAdmin: boolean | null
  isLoading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  session: null,
  user: null,
  isAdmin: null,
  isLoading: true,
  signOut: async () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const supabase = useMemo(() => createClient(), [])

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSession(session)
      if (session?.access_token) {
        try {
          const status = await getMyAdminStatus(session.access_token)
          setIsAdmin(status.is_admin)
        } catch {
          setIsAdmin(false)
        }
      } else {
        setIsAdmin(null)
      }
      setIsLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (!session?.access_token) {
        setIsAdmin(null)
      } else {
        getMyAdminStatus(session.access_token)
          .then((status) => setIsAdmin(status.is_admin))
          .catch(() => setIsAdmin(false))
      }
      setIsLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [supabase])

  const signOut = async () => {
    await supabase.auth.signOut()
    setSession(null)
    setIsAdmin(null)
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        isAdmin,
        isLoading,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
