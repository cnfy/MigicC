"""Bounded-memory multipart body for requests file uploads."""
import os
import uuid
import time


class MultipartUpload:
    def __init__(self, fields, files, progress=None):
        self.boundary = uuid.uuid4().hex
        self.parts = []
        self.length = 0
        self.progress = progress
        self.sent = self.total = 0
        self.last_report = 0
        for name, value in fields.items():
            self.add(f'--{self.boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8'))
        for field, (filename, source, mime) in files.items():
            filename = filename.replace('"', '%22').replace('\r', '%0D').replace('\n', '%0A')
            self.add(f'--{self.boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode('utf-8'))
            size = os.fstat(source.fileno()).st_size - source.tell()
            self.parts.append([source, size, True])
            self.total += size
            self.length += size
            self.add(b'\r\n')
        self.add(f'--{self.boundary}--\r\n'.encode('ascii'))
        self.content_type = 'multipart/form-data; boundary=' + self.boundary

    def add(self, value):
        from io import BytesIO
        self.parts.append([BytesIO(value), len(value), False])
        self.length += len(value)

    def __len__(self):
        return self.length

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.length
        chunks = []
        while size and self.parts:
            source, remaining, is_file = self.parts[0]
            chunk = source.read(min(size, remaining))
            if not chunk and remaining:
                raise OSError('文件在上传期间发生变化，请重试。')
            chunks.append(chunk)
            size -= len(chunk)
            self.parts[0][1] -= len(chunk)
            if is_file:
                self.sent += len(chunk)
            if self.parts[0][1] == 0:
                self.parts.pop(0)
        if self.progress:
            now = time.monotonic()
            if now - self.last_report >= 0.1 or not self.parts:
                self.progress(self.sent, self.total)
                self.last_report = now
        return b''.join(chunks)
