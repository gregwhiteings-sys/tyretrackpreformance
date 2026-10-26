"""Direct camera output selection; no extra device resize or neural processing."""
import os

def safe_preview():
    return os.environ.get('TYRETRACK_SAFE_PREVIEW', '').strip() == '1'

def live_output(camera):
    # ColorCamera.video is native NV12. getCvFrame() converts it on the host.
    return camera.preview if safe_preview() else camera.video

def live_size():
    return (480, 270) if safe_preview() else (640, 360)
