'use client'

import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface DropdownMenuProps {
  trigger: React.ReactNode
  children: React.ReactNode
  align?: 'left' | 'right'
}

export function DropdownMenu({ trigger, children, align = 'right' }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="focus:outline-none"
      >
        {trigger}
      </button>
      {open && (
        <div
          className={cn(
            'absolute top-full mt-2 z-50 min-w-[200px] rounded-md border bg-popover p-1 shadow-md',
            align === 'right' ? 'right-0' : 'left-0'
          )}
        >
          {children}
        </div>
      )}
    </div>
  )
}

interface DropdownItemProps {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'default' | 'destructive'
}

export function DropdownItem({ children, onClick, disabled, variant = 'default' }: DropdownItemProps) {
  return (
    <button
      type="button"
      className={cn(
        'flex w-full items-center rounded-sm px-3 py-2 text-sm transition-colors',
        disabled
          ? 'cursor-default text-muted-foreground'
          : variant === 'destructive'
            ? 'cursor-pointer text-destructive hover:bg-destructive/10'
            : 'cursor-pointer hover:bg-accent hover:text-accent-foreground'
      )}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

export function DropdownSeparator() {
  return <div className="my-1 h-px bg-border" />
}
