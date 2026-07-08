import re

from mcqgenrator.logger import logger

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
except ImportError:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = NoTranscriptFound = Exception


_ID_PATTERNS = [
    r"(?:v=|\/videos\/|embed\/|youtu\.be\/|\/v\/|\/e\/|watch\?v=|&v=)([A-Za-z0-9_-]{11})",
]


def extract_video_id(url: str) -> str:
    for pattern in _ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # bare ID pasted directly
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
        return url.strip()
    raise ValueError("Couldn't find a YouTube video ID in that URL.")


def transcript_segments_to_text(segments) -> str:
    """Join transcript segment dicts (each with a 'text' key) into flat prose."""
    return " ".join(seg["text"].strip() for seg in segments if seg.get("text"))


def read_youtube_transcript(url: str) -> str:
    if YouTubeTranscriptApi is None:
        raise Exception(
            "youtube-transcript-api isn't installed. Run: pip install youtube-transcript-api"
        )

    video_id = extract_video_id(url)
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        text = transcript_segments_to_text(segments)
        if not text.strip():
            raise ValueError("Transcript was empty.")
        return text
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.exception("No transcript available for %s", video_id)
        raise Exception(f"No transcript is available for this video: {e}")
    except Exception as e:
        logger.exception("Failed to fetch YouTube transcript")
        raise Exception(f"Couldn't fetch the transcript: {e}")
