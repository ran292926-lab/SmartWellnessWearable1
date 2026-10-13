"""Start the server: python app.py  ->  https://localhost:5050"""

import os

from wellness import create_app
from wellness.config import PROJECT_DIR
from wellness.tls import ensure_certificate

app = create_app()

if __name__ == "__main__":
    # SR16: serve over TLS. USE_TLS=0 is only for Google Colab, where Colab's
    # own HTTPS proxy provides TLS between the browser and Colab.
    ssl_context = None
    if os.environ.get("USE_TLS", "1") != "0":
        ssl_context = ensure_certificate(PROJECT_DIR / "instance")

    # debug stays off so error pages never show stack traces (SR19)
    app.run(host="localhost", port=5050, debug=False, ssl_context=ssl_context)
