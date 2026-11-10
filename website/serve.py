import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class WebsiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[COMPèRE Website] {self.address_string()} - {format % args}\n")


def serve():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, WebsiteHandler)
    url = f"http://localhost:{PORT}"
    print("=" * 65)
    print(f"  COMPèRE Corporate Website Server")
    print(f"  Running locally at: {url}")
    print(f"  Serving files from: {DIRECTORY}")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 65)

    if "--open" in sys.argv or "-o" in sys.argv:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[COMPèRE Website] Server shut down gracefully.")
        httpd.server_close()


if __name__ == "__main__":
    serve()
