interface ErrorInfo {
  message: string
  action?: string
  actionLabel?: string
  retryable: boolean
}

const ERROR_MAP: Record<string, ErrorInfo> = {
  RECIPE_NOT_FOUND: {
    message: 'レシピが見つかりません',
    action: '/staple',
    actionLabel: '主食を変更する',
    retryable: false,
  },
  RECIPE_POOL_EXHAUSTED: {
    message: 'レシピの候補が不足しています。主食を変更するか、クラシックモードをお試しください',
    action: '/staple',
    actionLabel: '設定を変更する',
    retryable: false,
  },
  NETWORK_TIMEOUT: {
    message: '接続がタイムアウトしました。再試行してください',
    retryable: true,
  },
  VALIDATION_ERROR: {
    message: '入力内容に問題があります',
    retryable: false,
  },
  PLAN_NOT_FOUND: {
    message: 'プランが見つかりません',
    action: '/staple',
    actionLabel: 'プランを作成する',
    retryable: false,
  },
  GENERATION_FAILED: {
    message: 'プラン生成に失敗しました。再試行してください',
    retryable: true,
  },
  CONFLICT: {
    message: 'データが更新されました。ページを再読み込みしてください',
    retryable: true,
  },
  GOAL_NOT_FOUND: {
    message: '目標が設定されていません。先に設定を完了してください',
    action: '/setup',
    actionLabel: '設定する',
    retryable: false,
  },
  STAPLE_INVALID: {
    message: '選択された主食が無効です',
    action: '/staple',
    actionLabel: '主食を選び直す',
    retryable: false,
  },
  PROFILE_CONFLICT: {
    message: 'プロフィールは既に登録されています',
    retryable: false,
  },
}

export function getErrorInfo(errorCode?: string): ErrorInfo {
  if (errorCode && ERROR_MAP[errorCode]) {
    return ERROR_MAP[errorCode]
  }
  return {
    message: 'エラーが発生しました。再試行してください',
    retryable: true,
  }
}
