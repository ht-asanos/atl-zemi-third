'use client'

import dynamic from 'next/dynamic'

const PlansContent = dynamic(() => import('./plans-content'), { ssr: false })

export default function PlansPage() {
  return <PlansContent />
}
