function formatLocalDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/** UTC ベースで次の月曜日を YYYY-MM-DD で返す */
export function getNextMondayUTC(): string {
  const now = new Date()
  const utcDay = now.getUTCDay()
  const daysUntilMonday = utcDay === 0 ? 1 : utcDay === 1 ? 0 : 8 - utcDay
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + daysUntilMonday))
  return next.toISOString().slice(0, 10)
}

/** ローカルタイムで今日を YYYY-MM-DD で返す */
export function getTodayLocal(): string {
  return formatLocalDate(new Date())
}

/** ローカルタイムで指定日の月曜日を YYYY-MM-DD で返す */
export function getMondayOfDateLocal(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  d.setDate(d.getDate() + diff)
  return formatLocalDate(d)
}
