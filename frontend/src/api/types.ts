export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Employee {
  id: number;
  last_name: string | null;
  first_name: string | null;
  father_name: string | null;
  full_name: string;
  organization: number | null;
  organization_name: string | null;
  department: number | null;
  department_name: string | null;
  region: number | null;
  region_name: string | null;
  rank: number | null;
  rank_name: string | null;
  phone: string | null;
}

export interface Me {
  username: string;
  is_superuser: boolean;
  employee: Employee | null;
  permissions: string[];
}

export interface Organization {
  id: number;
  name: string;
  contract: string | null;
  inn: string | null;
  type: "worker" | "client";
}

export interface Unit {
  id: number;
  name: string;
}

export interface MaterialCategory {
  id: number;
  name: string;
}

export interface Material {
  id: number;
  category: number | null;
  category_name: string | null;
  employee: number | null;
  employee_name: string | null;
  unit: number | null;
  unit_name: string | null;
  name: string;
  number: number;
  code: string | null;
  price: string | null;
  year: string | null;
  image: string | null;
}

export interface Technics {
  id: number;
  name: string;
  parametr: string | null;
  inventory: string | null;
  serial: string | null;
  mac: string | null;
  ip: string | null;
  status: "free" | "active" | "repair" | "defect";
  status_display: string;
  organization: number | null;
  organization_name: string | null;
  region: number | null;
  region_name: string | null;
  employee: number | null;
  employee_name: string | null;
}

export interface Goal {
  id: number;
  organization: number | null;
  organization_name: string | null;
  name: string;
}

export interface OrderMaterialItem {
  id: number;
  material: number;
  material_name: string;
  unit_name: string | null;
  number: number;
  given: number | null;
  given_summa: string;
}

export interface Order {
  id: number;
  goal: number | null;
  goal_name: string | null;
  goal_organization_id: number | null;
  goal_organization_name: string | null;
  sender: number | null;
  sender_name: string | null;
  message_sender: string | null;
  receiver: number | null;
  receiver_name: string | null;
  user: number | null;
  user_name: string | null;
  status: string;
  status_display: string;
  date_creat: string;
  materials: OrderMaterialItem[];
}

export interface DeedConsent {
  id: number;
  deed: number;
  employee: number;
  employee_name: string;
  message: string | null;
  status: "viewed" | "approved" | "rejected";
  status_display: string;
  date_creat: string;
  date_edit: string;
}

export interface Deed {
  id: number;
  organization: number | null;
  organization_name: string | null;
  sender: number | null;
  sender_name: string | null;
  message_sender: string | null;
  status_sender: string;
  status_sender_display: string;
  receiver: number | null;
  receiver_name: string | null;
  user: number | null;
  user_name: string | null;
  body: string;
  status: string;
  status_display: string;
  file: string | null;
  code: string | null;
  date_creat: string;
  consents: DeedConsent[];
}
