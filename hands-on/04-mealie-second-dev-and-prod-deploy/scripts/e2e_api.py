"""End-to-end check for the recipe difficulty field and the AI summary endpoint.

Runs against a locally started Mealie instance (default http://127.0.0.1:9000).
Set BASE_URL to target another instance, e.g. the nginx front of the prod stack:
    BASE_URL=http://127.0.0.1:8080 python scripts/e2e_api.py
All requests and responses are printed so the run can be kept as evidence.
"""

import json
import os
import sys

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:9000")
USERNAME = "admin"
PASSWORD = "MyPassword"

# Only used when the dev seed data is absent (fresh, unseeded database).
REGISTER = {
    "email": "e2e@example.com",
    "username": "e2e",
    "full_name": "E2E",
    "password": "Password123!",
    "passwordConfirm": "Password123!",
    "group": "E2E Group",
    "household": "E2E Family",
    "seedData": False,
}


def show(step: str, response: httpx.Response) -> None:
    print(f"\n>>> {step} -> {response.status_code}")
    text = response.text
    print(text[:1200])


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, timeout=180)

    about = client.get("/api/app/about")
    show("GET /api/app/about", about)

    token = ""

    login = client.post(
        "/api/auth/token",
        data={"username": USERNAME, "password": PASSWORD},
    )
    show("POST /api/auth/token (before register)", login)

    if login.status_code != 200:
        register = client.post("/api/users/register", json=REGISTER)
        show("POST /api/users/register", register)

        login = client.post(
            "/api/auth/token",
            data={"username": REGISTER["username"], "password": REGISTER["password"]},
        )
        show("POST /api/auth/token", login)

    if login.status_code == 200:
        token = login.json()["access_token"]

    if not token:
        print("FATAL: no access token")
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "番茄炒蛋",
        "description": "家常快手菜，甜咸口。",
        "difficulty": "medium",
        "recipe_yield": "2 人份",
        "prep_time": "5",
        "cook_time": "10",
        "total_time": "15",
        "recipe_ingredient": [
            {"note": "番茄 2 个"},
            {"note": "鸡蛋 3 个"},
            {"note": "白糖 1 小勺"},
        ],
        "recipe_instructions": [
            {"text": "番茄切块，鸡蛋打散。"},
            {"text": "热锅下油，炒散鸡蛋盛出。"},
            {"text": "下番茄炒出汁，加糖，回锅鸡蛋炒匀。"},
        ],
    }

    # `POST /api/recipes` only accepts a name; everything else is written by
    # `PUT /api/recipes/{slug}` with the full recipe payload.
    created = client.post("/api/recipes", json={"name": payload["name"]}, headers=headers)
    show("POST /api/recipes (name only)", created)

    if created.status_code >= 400:
        print("FATAL: recipe creation failed")
        return 1

    slug = created.json()
    print("slug:", slug)

    fetched = client.get(f"/api/recipes/{slug}", headers=headers)
    if fetched.status_code != 200:
        print("FATAL: cannot read created recipe", fetched.status_code, fetched.text[:400])
        return 1

    summary = fetched.json()
    print(">>> difficulty before update =", repr(summary.get("difficulty")))

    update_body = {
        **summary,
        "name": "番茄炒蛋 E2E",
        "description": payload["description"],
        "difficulty": "medium",
        "recipeYield": payload["recipe_yield"],
        "prepTime": payload["prep_time"],
        "cookTime": payload["cook_time"],
        "totalTime": payload["total_time"],
        "recipeIngredient": [
            {"originalText": "番茄 2 个"},
            {"originalText": "鸡蛋 3 个"},
            {"originalText": "白糖 1 小勺"},
        ],
        "recipeInstructions": [
            {"text": "番茄切块，鸡蛋打散。"},
            {"text": "热锅下油，炒散鸡蛋盛出。"},
            {"text": "下番茄炒出汁，加糖，回锅鸡蛋炒匀。"},
        ],
    }
    update_body.pop("slug", None)

    updated = client.put(f"/api/recipes/{slug}", json=update_body, headers=headers)
    show("PUT /api/recipes/{slug} (difficulty=medium)", updated)

    if updated.status_code != 200:
        print("FATAL: update failed")
        return 1

    slug = updated.json()["slug"]

    refetched = client.get(f"/api/recipes/{slug}", headers=headers)
    print(">>> difficulty after update =", repr(refetched.json().get("difficulty")))

    update_body["difficulty"] = "hard"
    update_body["name"] = "番茄炒蛋 E2E Hard"
    second = client.put(f"/api/recipes/{slug}", json=update_body, headers=headers)
    show("PUT /api/recipes/{slug} (difficulty=hard)", second)

    if second.status_code == 200:
        slug = second.json()["slug"]

    third = client.get(f"/api/recipes/{slug}", headers=headers)
    print(">>> difficulty after second update =", repr(third.json().get("difficulty")))

    ai = client.post(f"/api/recipes/{slug}/ai-summary", headers=headers)
    show("POST /api/recipes/{slug}/ai-summary", ai)

    if ai.status_code == 200:
        body = ai.json()
        print("\n>>> AI SUMMARY JSON <<<")
        print(json.dumps(body, ensure_ascii=False, indent=2))

    blank = client.post("/api/recipes/does-not-exist/ai-summary", headers=headers)
    show("POST /api/recipes/does-not-exist/ai-summary", blank)

    return 0


if __name__ == "__main__":
    sys.exit(main())
