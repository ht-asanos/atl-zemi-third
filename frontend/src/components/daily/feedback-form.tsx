'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

interface FeedbackFormProps {
  onSubmit: (text: string) => void
  isLoading: boolean
}

export function FeedbackForm({ onSubmit, isLoading }: FeedbackFormProps) {
  const [text, setText] = useState('')

  const handleSubmit = () => {
    if (text.trim()) {
      onSubmit(text.trim())
    }
  }

  return (
    <div className="space-y-2">
      <Label>感想・フィードバック</Label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="例: トレーニングがきつすぎた、主食に飽きた..."
        maxLength={1000}
        rows={3}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{text.length}/1000</span>
        <Button onClick={handleSubmit} disabled={isLoading || !text.trim()} size="sm">
          {isLoading ? '送信中...' : 'フィードバック送信'}
        </Button>
      </div>
    </div>
  )
}
