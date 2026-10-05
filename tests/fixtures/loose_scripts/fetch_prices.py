import json
import urllib.request

URL = "https://api.example.com/prices"

with urllib.request.urlopen(URL) as resp:
    print(json.load(resp))
