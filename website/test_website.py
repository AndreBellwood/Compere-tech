import os
import threading
import urllib.request
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler


def test_html_content():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    assert os.path.exists(path), f"File {path} does not exist"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    assert len(content) > 5000, f"HTML file too small: {len(content)} bytes"
    assert "COMPèRE" in content, "Branding COMPèRE missing"
    assert "Technical Compliance Terminal" in content, "Terminal title missing"
    assert "matrix-preview" in content, "Matrix preview section missing"
    assert "capabilities" in content, "Capabilities section missing"
    assert "workflow" in content, "Workflow section missing"
    assert "confidentiality" in content, "Confidentiality section missing"
    assert "compere-tech.streamlit.app" in content, "Terminal launch link missing"
    assert "COMPERE_Beta_Test_Pack.zip" in content, "Sample test pack download link missing"
    print(f"[PASS] HTML structure and required sections verified ({len(content)} bytes).")


def test_http_server():
    dir_path = os.path.dirname(__file__)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=dir_path, **kwargs)

    test_port = 8899
    server = HTTPServer(("127.0.0.1", test_port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    try:
        url = f"http://127.0.0.1:{test_port}/index.html"
        req = urllib.request.Request(url, headers={"User-Agent": "TestClient"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200, f"Expected status 200, got {resp.status}"
            body = resp.read().decode("utf-8")
            assert "COMPèRE" in body, "Response body missing COMPèRE"
            print("[PASS] Local HTTP server successfully serves landing page with 200 OK.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_html_content()
    test_http_server()
    print("ALL WEBSITE TESTS PASSED!")
