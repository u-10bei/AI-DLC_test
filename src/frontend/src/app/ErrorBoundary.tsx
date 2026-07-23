/**
 * LC-FE-06 ErrorBoundary (PAT-FE-50).
 *
 * Catches render-time exceptions so one broken screen does not take down the whole
 * app. API/network errors are handled separately (ApiError + ErrorBanner, PAT-FE-13).
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // Intentionally no internal detail is surfaced to the UI (SECURITY-09 posture).
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" data-testid="app-error-boundary">
          <h1>エラーが発生しました</h1>
          <p>画面の表示中に問題が発生しました。ページを再読み込みしてください。</p>
        </div>
      )
    }
    return this.props.children
  }
}
