"""Latest-only background PNG encoder; Qt widget capture stays on the GUI thread."""
import os,threading
from pathlib import Path

class SnapshotWriter:
    def __init__(self,path,on_error):
        self.path=Path(path);self.on_error=on_error;self.lock=threading.Lock()
        self.pending=None;self.running=False;self.thread=None
    def request(self,image):
        with self.lock:
            self.pending=image.copy()
            if self.running:return
            self.running=True
            self.thread=threading.Thread(target=self._run,name='TyreTrack dashboard PNG',daemon=True)
            self.thread.start()
    def _run(self):
        while True:
            with self.lock:
                image=self.pending;self.pending=None
                if image is None:self.running=False;return
            temporary=self.path.with_name(self.path.name+'.tmp')
            try:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                if not image.save(str(temporary),'PNG'):raise OSError('PNG save failed')
                os.replace(temporary,self.path)
            except Exception as exc:
                self.on_error(exc)
                try:temporary.unlink(missing_ok=True)
                except OSError:pass
    def wait(self,timeout=3):
        with self.lock:thread=self.thread
        if thread:thread.join(timeout)
        return thread is None or not thread.is_alive()
