"""Start the server: python app.py  ->  http://localhost:5000"""

from wellness import create_app

app = create_app()

if __name__ == "__main__":
    # debug stays off so error pages never show stack traces (SR19)
    app.run(host="localhost", port=5000, debug=False)
