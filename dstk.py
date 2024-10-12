import tkinter as tk
from PIL import Image, ImageTk
from pathlib import Path


class DsButton():
    def __init__(self, master, width=None, height=None, bg=None, scale=None):
        self.scale = scale
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self.img_left = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('button_left.png')).resize((self.adapt_size(60), self.adapt_size(26))))
        self.img_right = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('button_right.png')).resize((self.adapt_size(60), self.adapt_size(26))))
        self.label = tk.Label(master, image=self.img_left, cursor='hand2', width=width, height=height, bg=bg)
        self.value = 0
        self.command = None
        self.bind()

    def adapt_size(self, value):
        if value:
            return int(value * self.scale)
        else:
            return None

    def bind(self):
        self.label.bind('<Button-1>', self.onchange)

    def onchange(self, event):
        if self.value == 0:
            self.label.config(image=self.img_right)
            self.value = 1
        elif self.value == 1:
            self.label.config(image=self.img_left)
            self.value = 0
        if self.command:
            self.command(self.value)

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)

    def pack(self, *args, **kwargs):
        self.label.pack(*args, **kwargs)

    def place(self, *args, **kwargs):
        self.label.place(*args, **kwargs)

    def config(self, command):
        self.command = command

    def setvalue(self, value):
        if value == 0:
            self.value = 0
            self.label.config(image=self.img_left)
        if value == 1:
            self.value = 1
            self.label.config(image=self.img_right)

    def getvalue(self):
        return self.value
