import { TrainingTreeClient } from './training-tree-client'
import { getTodayLocal } from '@/lib/date-utils'
import type { TrainingEquipment } from '@/types/plan'

const DEFAULT_EQUIPMENT: TrainingEquipment[] = ['none']

interface TrainingTreePageProps {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}

export default async function TrainingTreePage({ searchParams }: TrainingTreePageProps) {
  const params = (await searchParams) ?? {}
  const startDateParam = params.start_date
  const startDate = typeof startDateParam === 'string' ? startDateParam : getTodayLocal()

  const rawEquipment = params.available_equipment
  const availableEquipment = (
    Array.isArray(rawEquipment)
      ? rawEquipment
      : typeof rawEquipment === 'string'
        ? [rawEquipment]
        : DEFAULT_EQUIPMENT
  ) as TrainingEquipment[]

  return (
    <TrainingTreeClient
      startDate={startDate}
      availableEquipment={availableEquipment.length ? availableEquipment : DEFAULT_EQUIPMENT}
    />
  )
}
