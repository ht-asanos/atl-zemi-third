import type { TrainingEquipment } from '@/types/plan'

export function buildTrainingSkillTreeHref(
  startDate: string,
  availableEquipment: TrainingEquipment[] | string[] | null | undefined
): string {
  const params = new URLSearchParams()
  params.set('start_date', startDate)
  const equipment = availableEquipment && availableEquipment.length ? availableEquipment : ['none']
  for (const item of equipment) {
    params.append('available_equipment', item)
  }
  return `/training-tree?${params.toString()}`
}
