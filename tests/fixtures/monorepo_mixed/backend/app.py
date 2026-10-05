from flask import Flask, jsonify

app = Flask(__name__)

PRODUCTS = [{"id": 1, "name": "Mug"}, {"id": 2, "name": "T-shirt"}]


@app.get("/api/products")
def products():
    return jsonify(PRODUCTS)


if __name__ == "__main__":
    app.run(port=5000)
