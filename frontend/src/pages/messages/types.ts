// /api/v1/spa/messages/deeds/ javobi (api/spa/messages.py: MessagesDeedSerializer = api DeedSerializer + *_info).

export type SignStatus = 'viewed' | 'approved' | 'rejected'
export type DeedKind = 'document' | 'svod' | 'reestr' | 'act' | 'petition' | 'service'

export interface DeedPerson {
  id: number
  full_name: string
  organization_name: string | null
  rank_name: string | null
  region_name: string | null
}

export interface DeedConsent {
  id: number
  deed: number
  employee: number | null
  employee_name: string | null
  employee_organization: string | null
  employee_rank: string | null
  message: string | null
  status: SignStatus
  status_display: string
  date_creat: string
  date_edit: string
}

export interface DeedAttachment {
  id: number
  file: string
}

export interface Deed {
  id: number
  code: string | null
  status: DeedKind
  status_display: string
  organization: number | null
  organization_name: string | null
  file: string | null
  body: string | null
  date_creat: string
  message_user: string | null
  user_edit: boolean

  sender: number | null
  status_sender: SignStatus
  date_sender: string | null
  message_sender: string | null
  receiver: number | null
  status_receiver: SignStatus
  date_receiver: string | null
  message_receiver: string | null
  sender_can_add_consent: boolean
  receiver_can_add_consent: boolean

  user_info: DeedPerson | null
  sender_info: DeedPerson | null
  receiver_info: DeedPerson | null
  consents: DeedConsent[]
  attachments: DeedAttachment[]

  can_edit: boolean
  can_manage_consents: boolean
  can_add_consents: boolean
  can_reject: boolean
  my_consent_id: number | null
}

/** deed_status (kod bo'yicha) — matnsiz va amal bayroqlarisiz */
export type PublicDeed = Pick<
  Deed,
  | 'id'
  | 'code'
  | 'file'
  | 'status'
  | 'status_display'
  | 'organization_name'
  | 'date_creat'
  | 'message_user'
  | 'status_sender'
  | 'date_sender'
  | 'message_sender'
  | 'receiver'
  | 'status_receiver'
  | 'date_receiver'
  | 'message_receiver'
  | 'consents'
  | 'user_info'
  | 'sender_info'
  | 'receiver_info'
>

export interface EmployeeOption {
  id: number
  full_name: string
  rank_name: string | null
}

export interface EditOptions {
  sender: EmployeeOption[]
  receiver: EmployeeOption[]
  agreements: EmployeeOption[]
  selected_agreements: number[]
}
