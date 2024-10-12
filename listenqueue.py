from queue import Queue
from threading import Thread

def worker(q):
    while True:
        func = q.get()
        func()
        q.task_done()

def start_queue(max=0):
    q = Queue(maxsize=max)
    worker_thread = Thread(target=worker, args=(q,))
    worker_thread.setDaemon(True)
    worker_thread.start()
    return q