"""Portable WAV imports and a persisted shuffle bag for celebration playback."""
import hashlib
import random
import wave
from pathlib import Path


def validate_wav(path):
    path = Path(path)
    if path.stat().st_size > 12 * 1024 * 1024:
        raise ValueError('Choose a WAV smaller than 12 MB.')
    try:
        with wave.open(str(path), 'rb') as w:
            if w.getcomptype() != 'NONE' or w.getsampwidth() != 2 or w.getnchannels() not in (1, 2):
                raise ValueError('Use uncompressed 16-bit PCM WAV, mono or stereo.')
            seconds = w.getnframes() / w.getframerate()
            if not 0 < seconds <= 60:
                raise ValueError('Choose a celebration between 0 and 60 seconds long.')
            expected = w.getnframes() * w.getnchannels() * w.getsampwidth()
            if len(w.readframes(w.getnframes())) != expected:
                raise ValueError('The WAV is incomplete; export it again.')
    except (wave.Error, EOFError) as exc:
        raise ValueError('Use an uncompressed 16-bit PCM WAV file.') from exc
    return seconds


def import_wav(source, folder):
    source, folder = Path(source), Path(folder)
    validate_wav(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    # Hash identity prevents duplicate imports and unsafe filenames.
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (digest + '.wav')
    if not destination.exists():
        destination.write_bytes(source.read_bytes())
    label = source.stem.replace('\n', ' ').replace('\r', ' ')[:80]
    (folder / (digest + '.txt')).write_text(label, encoding='utf-8')
    return 'custom_' + digest


def catalog(bundled, folder):
    result = dict(bundled)
    for path in sorted(Path(folder).glob('*.wav')):
        try:
            validate_wav(path)
            label_path = path.with_suffix('.txt')
            label = label_path.read_text(encoding='utf-8')[:80] if label_path.exists() else path.stem
            result['custom_' + path.stem] = ('Added · ' + label, str(path.resolve()))
        except (OSError, ValueError, UnicodeError):
            continue
    return result


def plan_shuffle(available, state, rng=None):
    """Return next key and next state; caller commits only after playback starts."""
    rng = rng or random
    keys = list(dict.fromkeys(available))
    if not keys:
        raise ValueError('No available celebration WAV files.')
    state = state if isinstance(state, dict) else {}
    remaining = state.get('remaining', [])
    remaining = remaining if isinstance(remaining, list) else []
    remaining = list(dict.fromkeys(k for k in remaining if isinstance(k, str) and k in keys))
    # Refill if the catalog changed so a newly imported sound joins the next cycle.
    if state.get('catalog') != sorted(keys) or not remaining:
        remaining = keys.copy()
        rng.shuffle(remaining)
    if len(remaining) > 1 and remaining[0] == state.get('last'):
        remaining[0], remaining[1] = remaining[1], remaining[0]
    key = remaining.pop(0)
    return key, dict(last=key, remaining=remaining, catalog=sorted(keys))
