import requests
from main.services.translit import cyr_to_lat


BASE_URL = "https://hrdev.imv.uz/api/v1/state/internal/organizations/by-tin"
AUTH_USER = "crm"
AUTH_PASS = "qwec34s"


def fetch_all_employees(tin: str):
    all_emps = []
    page = 1   # ❗ API 1-sahifadan boshlanadi

    while True:

        url = f"{BASE_URL}/{tin}/employees/"
        params = {
            "page": page,
            "size": 100
        }

        print(f"➡ Sahifa: {page}")

        res = requests.get(
            url,
            auth=(AUTH_USER, AUTH_PASS),
            params=params,
            timeout=20
        )

        if res.status_code == 404:
            print("🔚 Oxirgi sahifa (404 qaytdi)")
            break

        if res.status_code != 200:
            print("❌ API ERROR:", res.status_code, res.text)
            break

        data = res.json()
        content = data.get("content", [])

        if not content:
            print("🔚 Ma’lumot tugadi")
            break

        # FIO → Lotin
        for emp in content:
            emp["full_name"] = cyr_to_lat(emp.get("full_name", ""))

        all_emps.extend(content)

        print(f"✔ Yuklandi: {len(content)} ta (jami {len(all_emps)})")

        page += 1

    return all_emps
