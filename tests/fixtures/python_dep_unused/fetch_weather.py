import sys

import requests

API = "https://wttr.in/{city}?format=3"


def fetch(city: str) -> str:
    return requests.get(API.format(city=city), timeout=10).text


if __name__ == "__main__":
    print(fetch(sys.argv[1] if len(sys.argv) > 1 else "Lisbon"))
