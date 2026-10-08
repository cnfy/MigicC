from queue import Queue, Empty
from tkinter import TclError

def start_queue(owner, max=0):
    queue = Queue(maxsize=max)
    def drain():
        for _ in range(20):
            try:
                callback = queue.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception:
                import sys
                owner.report_callback_exception(*sys.exc_info())
            finally:
                queue.task_done()
        try:
            if owner.winfo_exists():
                owner.after(20, drain)
        except TclError:
            pass  # A queued callback can close the application.
    owner.after(20, drain)
    return queue
