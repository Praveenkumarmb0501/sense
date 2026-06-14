import sys
import subprocess
import time
import socket
import os

# CRITICAL: Chromium flags MUST be set before QApplication is created
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join([
    "--use-fake-ui-for-media-stream",
    "--enable-media-stream",
    "--auto-accept-camera-and-microphone-capture",
    "--unsafely-treat-insecure-origin-as-secure=http://localhost:3000",
    "--disable-features=MediaStreamTrackInternals",
])

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl


def wait_for_port(port, host='localhost', timeout=30.0):
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.5)
    return False


class DebugPage(QWebEnginePage):
    """Custom page that logs all JS console messages to the Python terminal."""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        level_str = ["INFO", "WARNING", "ERROR"][level] if level < 3 else "DEBUG"
        print(f"[JS {level_str}] {message}  (line {lineNumber})")

    # Catch the permission request via the old deprecated hook as a fallback
    def featurePermissionRequested(self, url, feature):
        self.setFeaturePermission(
            url, feature,
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
        )
        print(f"[Legacy Permission Granted] {feature}")


class ReactDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Speak Sense – React Desktop")
        self.resize(1024, 768)

        # Use the custom debug page so we can see JS console output
        page = DebugPage()
        self.browser = QWebEngineView()
        self.browser.setPage(page)

        # Enable media-related settings
        s = page.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # ---------- Permission handling (new API for PyQt6 ≥ 6.8) ----------
        try:
            page.permissionRequested.connect(self._grant_new)
            print("[Setup] Connected new permissionRequested signal")
        except AttributeError:
            pass

        # ---------- Permission handling (legacy API for PyQt6 < 6.8) ----------
        try:
            page.featurePermissionRequested.connect(self._grant_legacy)
            print("[Setup] Connected legacy featurePermissionRequested signal")
        except AttributeError:
            pass

        self.setCentralWidget(self.browser)
        self.browser.setUrl(QUrl("http://localhost:3000"))

    # --- new API (Qt ≥ 6.8) ---
    @staticmethod
    def _grant_new(permission):
        permission.grant()
        print(f"[Permission Granted] type={permission.permissionType()}")

    # --- legacy API ---
    def _grant_legacy(self, url, feature):
        self.browser.page().setFeaturePermission(
            url, feature,
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
        )
        print(f"[Permission Granted] feature={feature}  url={url.toString()}")


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # ---- Start Vite dev server ----
    print("Starting React dev server…")
    server = subprocess.Popen(
        ["cmd", "/c", "npm run dev"],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    print("Waiting for Vite on port 3000…")
    if not wait_for_port(3000, timeout=20.0):
        print("⚠  Timeout – make sure 'npm install' has been run.")

    # ---- Launch desktop window ----
    app = QApplication(sys.argv)
    win = ReactDesktopApp()
    win.show()
    app.exec()

    # ---- Cleanup ----
    print("Shutting down dev server…")
    server.kill()


if __name__ == "__main__":
    main()
