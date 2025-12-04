"""
System Control - Control applications, files, and websites
"""
import os
import subprocess
import webbrowser
import platform
from pathlib import Path
from typing import Optional, List
from friday.utils.logger import get_logger

logger = get_logger("system_control")


class SystemControl:
    """System control for opening apps, files, and websites"""

    def __init__(self):
        self.system = platform.system()
        self.common_apps = self._get_common_apps()
        logger.info(f"System Control initialized for {self.system}")

    def _get_common_apps(self) -> dict:
        """Get common application paths for the current OS"""
        if self.system == "Windows":
            return {
                # Browsers
                "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
                "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",

                # Office
                "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
                "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
                "powerpoint": r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",

                # Communication
                "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
                "slack": os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe"),
                "teams": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Teams\current\Teams.exe"),

                # Media
                "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
                "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",

                # Development
                "vscode": os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
                "pycharm": r"C:\Program Files\JetBrains\PyCharm Community Edition 2023.3\bin\pycharm64.exe",

                # System
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "explorer": "explorer.exe",
            }
        elif self.system == "Darwin":  # macOS
            return {
                "chrome": "/Applications/Google Chrome.app",
                "firefox": "/Applications/Firefox.app",
                "safari": "/Applications/Safari.app",
                "spotify": "/Applications/Spotify.app",
                "vscode": "/Applications/Visual Studio Code.app",
            }
        else:  # Linux
            return {
                "chrome": "google-chrome",
                "firefox": "firefox",
                "spotify": "spotify",
                "vscode": "code",
            }

    def open_app(self, app_name: str) -> bool:
        """
        Open an application by name

        Args:
            app_name: Application name (e.g., "chrome", "spotify")

        Returns:
            bool: True if successful
        """
        try:
            app_name_lower = app_name.lower()

            # Check if it's a known app
            if app_name_lower in self.common_apps:
                app_path = self.common_apps[app_name_lower]

                if self.system == "Windows":
                    # Check if file exists
                    if os.path.exists(app_path):
                        os.startfile(app_path)
                        logger.info(f"Opened {app_name} from {app_path}")
                        return True
                    else:
                        # Try running directly (for system apps)
                        subprocess.Popen([app_path], shell=True)
                        logger.info(f"Launched {app_name}")
                        return True

                elif self.system == "Darwin":  # macOS
                    subprocess.Popen(["open", app_path])
                    logger.info(f"Opened {app_name}")
                    return True

                else:  # Linux
                    subprocess.Popen([app_path])
                    logger.info(f"Opened {app_name}")
                    return True

            else:
                # Try to run as command
                if self.system == "Windows":
                    subprocess.Popen(app_name, shell=True)
                else:
                    subprocess.Popen([app_name])

                logger.info(f"Attempted to launch {app_name} as command")
                return True

        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")
            return False

    def open_file(self, file_path: str) -> bool:
        """
        Open a file with default application

        Args:
            file_path: Path to file

        Returns:
            bool: True if successful
        """
        try:
            path = Path(file_path)

            if not path.exists():
                logger.warning(f"File not found: {file_path}")
                return False

            if self.system == "Windows":
                os.startfile(str(path))
            elif self.system == "Darwin":  # macOS
                subprocess.Popen(["open", str(path)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(path)])

            logger.info(f"Opened file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to open file {file_path}: {e}")
            return False

    def open_folder(self, folder_path: str) -> bool:
        """
        Open a folder in file explorer

        Args:
            folder_path: Path to folder

        Returns:
            bool: True if successful
        """
        try:
            path = Path(folder_path)

            if not path.exists():
                logger.warning(f"Folder not found: {folder_path}")
                return False

            if self.system == "Windows":
                os.startfile(str(path))
            elif self.system == "Darwin":  # macOS
                subprocess.Popen(["open", str(path)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(path)])

            logger.info(f"Opened folder: {folder_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to open folder {folder_path}: {e}")
            return False

    def open_url(self, url: str) -> bool:
        """
        Open URL in default browser

        Args:
            url: URL to open

        Returns:
            bool: True if successful
        """
        try:
            # Add https:// if not present
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            webbrowser.open(url)
            logger.info(f"Opened URL: {url}")
            return True

        except Exception as e:
            logger.error(f"Failed to open URL {url}: {e}")
            return False

    def search_google(self, query: str) -> bool:
        """
        Open Google search with query

        Args:
            query: Search query

        Returns:
            bool: True if successful
        """
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            return self.open_url(search_url)

        except Exception as e:
            logger.error(f"Failed to search Google: {e}")
            return False

    def run_command(self, command: str) -> bool:
        """
        Run a shell command

        Args:
            command: Shell command to run

        Returns:
            bool: True if successful
        """
        try:
            if self.system == "Windows":
                subprocess.Popen(command, shell=True)
            else:
                subprocess.Popen(command.split())

            logger.info(f"Executed command: {command}")
            return True

        except Exception as e:
            logger.error(f"Failed to execute command {command}: {e}")
            return False

    def get_common_locations(self) -> dict:
        """Get dictionary of common folder locations"""
        if self.system == "Windows":
            return {
                "desktop": os.path.expanduser("~/Desktop"),
                "documents": os.path.expanduser("~/Documents"),
                "downloads": os.path.expanduser("~/Downloads"),
                "pictures": os.path.expanduser("~/Pictures"),
                "music": os.path.expanduser("~/Music"),
                "videos": os.path.expanduser("~/Videos"),
            }
        else:
            return {
                "desktop": os.path.expanduser("~/Desktop"),
                "documents": os.path.expanduser("~/Documents"),
                "downloads": os.path.expanduser("~/Downloads"),
            }

    def list_available_apps(self) -> List[str]:
        """Get list of recognized application names"""
        return list(self.common_apps.keys())
