import requests
import math
from main.services.translit import cyr_to_lat

BASE_URL = "https://hrdev.imv.uz/api/v1/state/internal/organizations/by-tin"
AUTH_USER = "crm"
AUTH_PASS = "qwec34s"


def fetch_all_employees(tin: str):
    all_employees = []
    page = 1

    while True:
        url = f"{BASE_URL}/{tin}/employees/"
        params = {"page": page}

        print(f"➡ SO‘ROV: page={page}")

        res = requests.get(
            url,
            auth=(AUTH_USER, AUTH_PASS),
            params=params,
            timeout=20
        )

        if res.status_code != 200:
            print("❌ API ERROR:", res.status_code, res.text)
            break

        data = res.json()
        content = data.get("content", [])

        if not content:
            print("🔚 Ma’lumot tugadi")
            break

        # 🔤 KIRILL → LOTIN
        for emp in content:
            emp["full_name"] = cyr_to_lat(emp.get("full_name"))
            emp["position"] = cyr_to_lat(emp.get("position"))
            emp["department"] = cyr_to_lat(emp.get("department"))

        all_employees.extend(content)

        size = data.get("size", len(content))
        total = data.get("numberOfElements", len(all_employees))

        print(f"✔ Yuklandi: {len(content)} ta (jami {len(all_employees)})")

        pages_total = math.ceil(total / size)

        if page >= pages_total:
            print("🔚 Oxirgi sahifa")
            break

        page += 1

    return all_employees
