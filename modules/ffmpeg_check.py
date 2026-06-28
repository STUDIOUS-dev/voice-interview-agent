import os
import platform
import shutil
import sys


def _find_binary(name: str) -> str | None:
    
    path = shutil.which(name)
    if path:
        return path

    
    try:
        from pydub.utils import which as pydub_which
        path = pydub_which(name)
        if path:
            return path
    except Exception:
        pass

    return None


def _install_hint() -> str:
    os_name = platform.system()
    if os_name == "Darwin":
        return "  brew install ffmpeg"
    if os_name == "Linux":
        return "  sudo apt install ffmpeg   # Debian/Ubuntu\n  sudo dnf install ffmpeg   # Fedora/RHEL"
    
    return (
        "  1. Download from: https://ffmpeg.org/download.html\n"
        "  2. Extract the archive and locate the bin\\ folder.\n"
        "  3. Add the bin\\ folder (not individual .exe files) to your system PATH.\n"
        "  4. Restart your terminal and re-run the program."
    )


def ensure_ffmpeg(verbose: bool = True) -> None:
    from pydub import AudioSegment  

    ffmpeg_path = _find_binary("ffmpeg")
    ffprobe_path = _find_binary("ffprobe")

    missing = []
    if not ffmpeg_path:
        missing.append("ffmpeg")
    if not ffprobe_path:
        missing.append("ffprobe")

    if missing:
        print(
            f"\nERROR: The following FFmpeg binaries could not be found: {', '.join(missing)}\n"
            f"\n"
            f"  pydub requires FFmpeg to encode and decode audio.\n"
            f"  Searched PATH: {os.environ.get('PATH', '(empty)')}\n"
            f"\n"
            f"  Install FFmpeg:\n"
            f"{_install_hint()}\n"
            f"\n"
            f"  Alternatively, run with --mode text to bypass all audio entirely.\n"
        )
        sys.exit(1)

    
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffprobe   = ffprobe_path

    if verbose:
        print(f"[FFmpeg detected: {ffmpeg_path}]")
