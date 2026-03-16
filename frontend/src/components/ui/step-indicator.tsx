import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StepIndicatorProps {
  currentStep: 1 | 2
}

const steps = [
  { label: '初期設定' },
  { label: 'プラン生成' },
]

export function StepIndicator({ currentStep }: StepIndicatorProps) {
  return (
    <div className="mb-6 flex items-center justify-center gap-0">
      {steps.map((step, i) => {
        const stepNum = (i + 1) as 1 | 2
        const isCompleted = stepNum < currentStep
        const isCurrent = stepNum === currentStep

        return (
          <div key={stepNum} className="flex items-center">
            {i > 0 && (
              <div
                className={cn(
                  'h-0 w-8 border-t-2',
                  isCompleted ? 'border-primary' : 'border-muted'
                )}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium',
                  isCompleted && 'bg-primary text-primary-foreground',
                  isCurrent && 'ring-2 ring-primary bg-primary text-primary-foreground',
                  !isCompleted && !isCurrent && 'bg-muted text-muted-foreground'
                )}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : stepNum}
              </div>
              <span className={cn(
                'text-xs',
                isCurrent ? 'font-medium text-foreground' : 'text-muted-foreground'
              )}>
                {step.label}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
