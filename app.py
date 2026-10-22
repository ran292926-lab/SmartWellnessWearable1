"""Start the server: python app.py  ->  https://localhost:5050"""

import os

from wellness import create_app, server
from wellness.config import PROJECT_DIR
from wellness.tls import server_context

app = create_app()

# PR8, F5, F6: no client IP addresses in the server output and no version in the Server header
server.configure()

if __name__ == "__main__":
    # SR16: serve over TLS. USE_TLS=0 is only for Google Colab, where Colab's
    # own HTTPS proxy provides TLS between the browser and Colab.
    ssl_context = None
    if os.environ.get("USE_TLS", "1") != "0":
        ssl_context = server_context(PROJECT_DIR / "instance")

    # debug stays off so error pages never show stack traces (SR19)
    app.run(host="localhost", port=5050, debug=False, ssl_context=ssl_context, threaded=True)
