/**
 * App: assembles the providers and the route table. The ApiClient is created here so
 * its onUnauthorized is wired to the auth context (any 401 -> back to login, FE-50).
 */

import { useMemo } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'

import { ApiClient } from '../api/client'
import { ApiContext } from './apiContext'
import { AppShell } from './AppShell'
import { useAuth } from './AuthContext'
import { createQueryClient } from './queryClient'
import { AssignmentsView } from '../views/AssignmentsView'
import { DeclarationsView } from '../views/DeclarationsView'
import { EventView } from '../views/EventView'
import { LoginView } from '../views/LoginView'
import { MastersView } from '../views/MastersView'
import { OptimizeView } from '../views/OptimizeView'
import { SufficiencyView } from '../views/SufficiencyView'

// Backend base URL is externalised (NFR-M05/M03). Empty string = same origin, which
// is how the bundle is served in the PoC (U08-H4).
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export function App(): JSX.Element {
  const auth = useAuth()
  const api = useMemo(
    () => new ApiClient({ baseUrl: BASE_URL, onUnauthorized: auth.onUnauthorized }),
    [auth.onUnauthorized],
  )
  const queryClient = useMemo(() => createQueryClient(), [])

  return (
    <ApiContext.Provider value={api}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/login" element={<LoginView />} />
          <Route element={<AppShell />}>
            <Route path="/events" element={<EventView />} />
            <Route path="/masters" element={<MastersView />} />
            <Route path="/declarations" element={<DeclarationsView />} />
            <Route path="/sufficiency" element={<SufficiencyView />} />
            <Route path="/optimize" element={<OptimizeView />} />
            <Route path="/assignments" element={<AssignmentsView />} />
          </Route>
          <Route path="*" element={<Navigate to="/events" replace />} />
        </Routes>
      </QueryClientProvider>
    </ApiContext.Provider>
  )
}
