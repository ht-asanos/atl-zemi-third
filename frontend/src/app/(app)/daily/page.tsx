'use client'

import dynamic from 'next/dynamic'

const DailyContent = dynamic(() => import('./daily-content'), { ssr: false })

export default function DailyPage() {
  return <DailyContent />
}
