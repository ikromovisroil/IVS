// Ruscha lug'at: har bo'lim o'z faylida (kalit — o'zbekcha matn, qiymat — ruscha).
import common from './common'
import comms from './comms'
import dashboard from './dashboard'
import messages from './messages'
import orders from './orders'
import ordersBarn from './orders-barn'
import people from './people'
import reports from './reports'
import stats from './stats'
import warehouse from './warehouse'

export const RU: Record<string, string> = {
  ...common,
  ...dashboard,
  ...orders,
  ...ordersBarn,
  ...messages,
  ...warehouse,
  ...people,
  ...reports,
  ...stats,
  ...comms,
}
