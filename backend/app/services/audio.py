import mimetypes
import os
import io
import subprocess
import uuid
import wave
from pathlib import Path
import numpy as np
from fastapi import HTTPException, UploadFile
from ..config import get_settings

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
ALLOWED_MIME_PREFIXES = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/ogg", "application/ogg"}


def _signature_matches(ext: str, header: bytes) -> bool:
    if ext == ".wav":
        return header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    if ext == ".ogg":
        return header[:4] == b"OggS"
    if ext == ".m4a":
        return b"ftyp" in header[:32]
    if ext == ".mp3":
        return header[:3] == b"ID3" or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0)
    return False


async def save_audio(upload: UploadFile, upload_dir: str, max_mb: int, max_duration_seconds: int = 900) -> tuple[str, str, float | None]:
    original = Path(upload.filename or "audio").name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Unsupported audio format. Use WAV, MP3, M4A, or OGG.")
    if upload.content_type and upload.content_type not in ALLOWED_MIME_PREFIXES:
        guessed = mimetypes.guess_type(original)[0]
        if guessed not in ALLOWED_MIME_PREFIXES:
            raise HTTPException(415, "Audio MIME type does not match a supported format.")
    header = await upload.read(64 * 1024)
    await upload.seek(0)
    if not header or not _signature_matches(ext, header):
        raise HTTPException(415, "The file signature does not match the selected audio format.")
    target_dir = Path(upload_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    target = (target_dir / stored).resolve()
    if target.parent != target_dir:
        raise HTTPException(400, "Invalid upload path.")
    max_bytes = max_mb * 1024 * 1024
    size = 0
    try:
        with target.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413, f"Audio file exceeds the {max_mb} MB limit.")
                handle.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(500, "Could not store the audio file.") from exc
    scan_command = get_settings().clamscan_command
    if scan_command:
        try:
            scan = subprocess.run([scan_command, "--no-summary", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            target.unlink(missing_ok=True)
            raise HTTPException(503, "Malware scanning is unavailable; the upload was rejected.") from exc
        if scan.returncode != 0:
            target.unlink(missing_ok=True)
            raise HTTPException(422, "The uploaded audio failed the malware scan.")
    duration = audio_duration(target)
    if duration is not None and duration > max_duration_seconds:
        target.unlink(missing_ok=True)
        raise HTTPException(413, f"Audio duration exceeds the {max_duration_seconds} second limit.")
    return original, stored, duration


def audio_duration(path: Path) -> float | None:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav:
                return round(wav.getnframes() / wav.getframerate(), 3)
        except (wave.Error, OSError, ZeroDivisionError):
            return None
    try:
        from mutagen import File as MutagenFile
        metadata = MutagenFile(str(path))
        if metadata is not None and metadata.info and metadata.info.length:
            return round(float(metadata.info.length), 3)
    except Exception:
        pass
    try:
        from pydub import AudioSegment
        return round(len(AudioSegment.from_file(path)) / 1000, 3)
    except Exception:
        return None


def load_audio_samples(path: Path, sample_rate: int = 16000) -> tuple[np.ndarray, int]:
    """Decode WAV and compressed audio into a model-compatible mono array."""
    try:
        import librosa
        audio, actual_rate = librosa.load(str(path), sr=sample_rate, mono=True)
        return audio, actual_rate
    except Exception as original_error:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            import soundfile as sf
            result = subprocess.run([get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "wav", "-ar", str(sample_rate), "-ac", "1", "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            audio, actual_rate = sf.read(io.BytesIO(result.stdout), dtype="float32")
            return np.asarray(audio, dtype=np.float32), actual_rate
        except Exception as fallback_error:
            raise RuntimeError("Could not decode audio. Install the backend requirements or convert the file to WAV.") from fallback_error


def resolve_audio(upload_dir: str, stored_filename: str) -> Path:
    root = Path(upload_dir).resolve()
    candidate = (root / Path(stored_filename).name).resolve()
    if candidate.parent != root or not candidate.exists():
        raise FileNotFoundError("Audio file not found")
    return candidate
