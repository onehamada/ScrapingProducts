#!/usr/bin/env python3
"""
Exemplo simples de uso da API.
"""

import json

import requests


API_BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    payload = {
        "query": "gtx 1060",
        "platforms": ["olx", "mercadolivre"],
        "max_results": 5,
        "headless": False,
    }

    response = requests.post(f"{API_BASE_URL}/api/search", json=payload, timeout=300)
    response.raise_for_status()
    data = response.json()

    print(f"Busca: {data['query']}")
    print(f"Total de itens: {data['total_items']}")
    print(f"JSON combinado: {data['json_snapshot']}")
    print()

    for platform, result in data["results"].items():
        print(f"== {platform.upper()} ==")
        print(f"Sucesso: {result['success']}")
        print(f"Itens: {result['count']}")
        if result.get("error"):
            print(f"Erro: {result['error']}")
        if result.get("note"):
            print(f"Nota: {result['note']}")
        if result.get("html_snapshot"):
            print(f"HTML: {result['html_snapshot']}")

        for item in result["items"][:3]:
            print(
                json.dumps(
                    {
                        "title": item["title"],
                        "price": item["price"],
                        "url": item["url"],
                    },
                    ensure_ascii=False,
                )
            )
        print()


if __name__ == "__main__":
    main()
