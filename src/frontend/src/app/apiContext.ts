/**
 * Makes the single ApiClient available to any view via context, so the base URL and
 * the onUnauthorized wiring are configured in exactly one place (composition root:
 * main.tsx / App).
 */

import { createContext, useContext } from 'react'

import { ApiClient } from '../api/client'

export const ApiContext = createContext<ApiClient | null>(null)

export function useApi(): ApiClient {
  const client = useContext(ApiContext)
  if (client === null) throw new Error('useApi must be used within ApiContext.Provider')
  return client
}
