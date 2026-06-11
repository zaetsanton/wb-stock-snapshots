#!/usr/bin/env python3
"""
Автономный сборщик остатков WB для запуска в GitHub Actions.
Не зависит от EGGHEADS-инструментов — использует только стандартную библиотеку Python.

Использование:
    export WB_API_TOKEN=ваш_токен
    python3 wb_snapshot_standalone.py

Переменные окружения:
    WB_API_TOKEN        — обязательно, персональный API-токен WB
    OUTPUT_DIR          — опционально, папка для результатов (по умолчанию: Данные/Индекс Локализации/История остатков WB/)
"""

import csv
import datetime
import json
import os
import urllib.request
from pathlib import Path

API_URL = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
REQUIRED_FIELDS = [
    "snapshot_collected_at_utc",
    "nmId",
    "vendorCode",
    "techSize",
    "barcode",
    "warehouseName",
    "quantity",
    "inWayToClient",
    "inWayFromClient",
]


def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def snapshot_slug() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fetch_stocks(token: str, date_from: str) -> list[dict]:
    url = f"{API_URL}?dateFrom={date_from}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def normalize(item: dict, collected_at: str) -> dict:
    return {
        "snapshot_collected_at_utc": collected_at,
        "nmId": item.get("nmId"),
        "vendorCode": item.get("supplierArticle", ""),
        "techSize": item.get("techSize", ""),
        "barcode": item.get("barcode", ""),
        "warehouseName": item.get("warehouseName", ""),
        "quantity": item.get("quantity", 0),
        "inWayToClient": item.get("inWayToClient", 0),
        "inWayFromClient": item.get("inWayFromClient", 0),
    }


def main() -> int:
    token = os.environ.get("WB_API_TOKEN", "").strip()
    if not token:
        print("❌ Ошибка: не задана переменная окружения WB_API_TOKEN", file=os.sys.stderr)
        return 1

    project_root = Path(__file__).resolve().parents[3]
    output_dir = Path(os.environ.get("OUTPUT_DIR", project_root / "Данные" / "Индекс Локализации" / "История остатков WB" / "snapshots"))
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = output_dir.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    collected_at = now_utc_iso()
    slug = snapshot_slug()
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    print(f"📦 Сбор остатков WB — {slug}")
    print(f"   Дата запроса: {today}")

    try:
        items = fetch_stocks(token, today)
    except Exception as exc:
        print(f"❌ Ошибка запроса к WB API: {exc}", file=os.sys.stderr)
        return 1

    # Сохраняем сырой JSON
    raw_path = raw_dir / f"stocks-{slug}.json"
    with raw_path.open("w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
    print(f"   Сырой JSON сохранён: {raw_path}")

    # Нормализуем и сохраняем CSV
    rows = [normalize(item, collected_at) for item in items if isinstance(item, dict)]
    csv_path = output_dir / f"stock-snapshot-{slug}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in REQUIRED_FIELDS})

    print(f"   CSV сохранён: {csv_path}")
    print(f"   Строк в снимке: {len(rows)}")
    print(f"   Уникальных складов: {len({r['warehouseName'] for r in rows})}")
    print(f"   Уникальных nmId: {len({r['nmId'] for r in rows})}")
    print(f"   Строк без размера: {sum(1 for r in rows if not r['techSize'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
