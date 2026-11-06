"""PySide6 shell. Shared memory, networking, and audio do not run on this thread."""

from __future__ import annotations

import sys
from pathlib import Path

from coach_agent.config.settings import AgentSettings, app_data_dir
from coach_agent.core.agent import CoachAgent
from coach_agent.core.game import MemoryRunKey, WindowsRunKey, apply_launch_at_login


def run_app(settings: AgentSettings, *, minimized: bool, settings_dir: Path | None) -> int:
    from PySide6.QtCore import QThread, Qt, Signal
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFormLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )

    from coach_agent.__main__ import build_agent

    home = settings_dir or app_data_dir()

    class Worker(QThread):
        status = Signal(object)

        def __init__(self, agent: CoachAgent) -> None:
            super().__init__()
            self.agent = agent
            self._running = True

        def run(self) -> None:
            self.agent.link.start()
            while self._running:
                self.agent.tick()
                self.status.emit(self.agent.status)
                self.msleep(int(1000 / max(1, self.agent.settings.physics_hz)))

        def stop(self) -> None:
            self._running = False
            self.wait(2000)
            self.agent.close()

    class Window(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Assetto Corsa Coach Agent")
            self.resize(460, 420)
            self.agent = build_agent(settings, None, None, home)
            self.rows: dict[str, QLabel] = {}
            root = QWidget()
            layout = QVBoxLayout(root)
            notice = QLabel(self._notice())
            notice.setWordWrap(True)
            layout.addWidget(notice)
            for key, title in (
                ("game", "Assetto Corsa"),
                ("memory", "Shared memory"),
                ("backend", "Backend"),
                ("rates", "Rates"),
                ("audio", "Audio"),
                ("error", "Last error"),
            ):
                label = QLabel("—")
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.rows[key] = label
                form = QFormLayout()
                form.addRow(title, label)
                layout.addLayout(form)
            save = QPushButton("Save settings")
            save.clicked.connect(self.save_settings)
            self.backend_url = QLineEdit(settings.backend_url)
            self.token = QLineEdit(settings.auth_token)
            self.token.setEchoMode(QLineEdit.EchoMode.Password)
            self.talk_key = QLineEdit(settings.push_to_talk_key)
            self.minimized = QCheckBox("Start minimized to the tray")
            self.minimized.setChecked(settings.start_minimized)
            self.login = QCheckBox("Launch when Windows starts")
            self.login.setChecked(settings.launch_at_login)
            if sys.platform != "win32":
                self.login.setEnabled(False)
                self.login.setToolTip("Launch at login is applied on Windows.")
            form = QFormLayout()
            form.addRow("Backend URL", self.backend_url)
            form.addRow("Token", self.token)
            form.addRow("Push-to-talk", self.talk_key)
            layout.addLayout(form)
            layout.addWidget(self.minimized)
            layout.addWidget(self.login)
            layout.addWidget(save)
            audio = QLabel("Microphone and headset playback run on this PC. Speech engines run on the AI host.")
            audio.setWordWrap(True)
            layout.addWidget(audio)
            self.setCentralWidget(root)
            self.worker = Worker(self.agent)
            self.worker.status.connect(self.apply_status)
            self.worker.start()
            self._build_tray()
            if minimized:
                self.hide()

        def _notice(self) -> str:
            if self.agent.status.layout_confirmed:
                return "Shared-memory layout has been marked confirmed on this PC."
            return (
                "The shared-memory layout matches the in-game Assetto Corsa definitions, "
                "but this PC has not confirmed a live session yet. Compare speed, rpm, gear, "
                "pedals, lap, and track position with the game before trusting coaching."
            )

        def apply_status(self, status) -> None:
            self.rows["game"].setText("running" if status.game_running else "not running")
            self.rows["memory"].setText("open" if status.shared_memory_open else "closed")
            self.rows["backend"].setText(status.backend)
            self.rows["rates"].setText(
                f"physics {status.physics_rate_hz:.0f} Hz · graphics {status.graphics_rate_hz:.0f} Hz · "
                f"publish {status.publish_rate_hz:.0f} Hz"
            )
            self.rows["audio"].setText(f"push-to-talk {settings.push_to_talk_key} · devices follow Windows")
            self.rows["error"].setText(status.last_error or "none")
            if hasattr(self, "tray"):
                self.tray.setToolTip(f"Coach Agent · {self.rows['game'].text()} · {status.backend}")

        def save_settings(self) -> None:
            settings.backend_url = self.backend_url.text().strip()
            settings.auth_token = self.token.text().strip()
            settings.push_to_talk_key = self.talk_key.text().strip() or "V"
            settings.start_minimized = self.minimized.isChecked()
            settings.launch_at_login = self.login.isChecked() and sys.platform == "win32"
            path = settings.save(settings_dir)
            command = f'"{sys.executable}" -m coach_agent --minimized'
            store = WindowsRunKey() if sys.platform == "win32" else MemoryRunKey()
            if sys.platform == "win32":
                apply_launch_at_login(store, settings.launch_at_login, command)
            QMessageBox.information(self, "Settings saved", f"Saved {path}. Restart the agent to use the new backend.")

        def _build_tray(self) -> None:
            self.tray = QSystemTrayIcon(self)
            self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
            menu = QMenu()
            show = QAction("Show", self)
            show.triggered.connect(self.showNormal)
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.quit)
            menu.addAction(show)
            menu.addAction(quit_action)
            self.tray.setContextMenu(menu)
            self.tray.show()

        def closeEvent(self, event) -> None:
            event.ignore()
            self.hide()

        def quit(self) -> None:
            self.worker.stop()
            QApplication.quit()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = Window()
    if not minimized:
        window.show()
    return app.exec()
