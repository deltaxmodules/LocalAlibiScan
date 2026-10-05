import csv


def clean(path: str) -> list[dict]:
    with open(path, newline="") as fh:
        return [row for row in csv.DictReader(fh) if row.get("value")]


if __name__ == "__main__":
    print(len(clean("data.csv")))
