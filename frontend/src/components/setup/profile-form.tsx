'use client'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import type { CreateProfileRequest } from '@/types/profile'

const ACTIVITY_LABELS: Record<string, string> = {
  low: '低い',
  moderate_low: 'やや低い',
  moderate: '中程度',
  high: '高い',
}

interface ProfileFormProps {
  data: CreateProfileRequest
  onChange: (data: CreateProfileRequest) => void
}

export function ProfileForm({ data, onChange }: ProfileFormProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="age">年齢</Label>
        <Input
          id="age"
          type="number"
          min={10}
          max={120}
          value={data.age || ''}
          onChange={(e) => onChange({ ...data, age: Number(e.target.value) })}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="gender">性別</Label>
        <Select
          id="gender"
          value={data.gender}
          onChange={(e) => onChange({ ...data, gender: e.target.value as 'male' | 'female' })}
          required
        >
          <option value="male">男性</option>
          <option value="female">女性</option>
        </Select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="height">身長 (cm)</Label>
          <Input
            id="height"
            type="number"
            step="0.1"
            min={100}
            max={250}
            value={data.height_cm || ''}
            onChange={(e) => onChange({ ...data, height_cm: Number(e.target.value) })}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="weight">体重 (kg)</Label>
          <Input
            id="weight"
            type="number"
            step="0.1"
            min={30}
            max={200}
            value={data.weight_kg || ''}
            onChange={(e) => onChange({ ...data, weight_kg: Number(e.target.value) })}
            required
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="activity">活動レベル</Label>
        <Select
          id="activity"
          value={data.activity_level}
          onChange={(e) =>
            onChange({ ...data, activity_level: e.target.value as CreateProfileRequest['activity_level'] })
          }
          required
        >
          {Object.entries(ACTIVITY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
    </div>
  )
}
