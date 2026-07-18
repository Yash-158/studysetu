import { useState } from 'react'
import { RoleShell } from '../../components/RoleShell'
import { PeoplePage } from './PeoplePage'
import { PoolsPage } from './PoolsPage'

type Tab = 'people' | 'pools'

export function AdminShell() {
  const [tab, setTab] = useState<Tab>('people')

  return (
    <RoleShell roleLabel="Admin" wide>
      <div className="ss-tabs ss-no-print">
        <button className={`ss-tab ${tab === 'people' ? 'ss-tab-active' : ''}`} onClick={() => setTab('people')}>
          People
        </button>
        <button className={`ss-tab ${tab === 'pools' ? 'ss-tab-active' : ''}`} onClick={() => setTab('pools')}>
          Pools
        </button>
      </div>
      {tab === 'people' ? <PeoplePage /> : <PoolsPage />}
    </RoleShell>
  )
}
