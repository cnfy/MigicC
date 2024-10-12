import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

class Toolbar(tk.Frame):
    def __init__(self, master, scale=None):
        super().__init__(master)
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self.scale = scale
        self._width = self.adapt_size(200)
        self._height = self.adapt_size(20)
        self.bg_color = '#87CEFA'
        self.act_color = '#4682B4'
        self.config(bg=self.bg_color)
        self.add_button()

    def adapt_size(self, value):
        if value:
            return int(value * self.scale)
        else:
            return None

    def add_button(self):
        self.btn_size = self.adapt_size(30)
        self.image_size = self.adapt_size(35)
        check_image = Image.open(self.relative_to_assets('check.png')).resize((self.image_size,self.image_size))
        gif_image = Image.open(self.relative_to_assets('gif.png')).resize((self.image_size,self.image_size))
        undo_image = Image.open(self.relative_to_assets('undo.png')).resize((self.image_size,self.image_size))
        rect_image = Image.open(self.relative_to_assets('rectangle.png')).resize((self.image_size,self.image_size))
        save_image = Image.open(self.relative_to_assets('save.png')).resize((self.image_size,self.image_size))
        self.check_image = ImageTk.PhotoImage(check_image)
        self.gif_image = ImageTk.PhotoImage(gif_image)
        self.undo_image = ImageTk.PhotoImage(undo_image)
        self.rect_image = ImageTk.PhotoImage(rect_image)
        self.save_image = ImageTk.PhotoImage(save_image)

        self.confirm_btn = tk.Button(self, image=self.check_image, width=self.btn_size, height=self.btn_size,
                                     cursor='hand2', relief=tk.FLAT, bg=self.bg_color, activebackground=self.act_color,
                                     overrelief=tk.SUNKEN, anchor=tk.CENTER)
        self.gif_btn = tk.Button(self, image=self.gif_image, width=self.btn_size, height=self.btn_size,
                                     cursor='hand2', relief=tk.FLAT, bg=self.bg_color, activebackground=self.act_color,
                                     overrelief=tk.SUNKEN, anchor=tk.CENTER)
        self.undo_btn = tk.Button(self, image=self.undo_image, width=self.btn_size, height=self.btn_size,
                                     cursor='hand2', relief=tk.FLAT, bg=self.bg_color, activebackground=self.act_color,
                                     overrelief=tk.SUNKEN, anchor=tk.CENTER)
        self.mark_btn = tk.Button(self, image=self.rect_image, width=self.btn_size, height=self.btn_size,
                                     cursor='hand2', relief=tk.FLAT, bg=self.bg_color, activebackground=self.act_color,
                                     overrelief=tk.SUNKEN, anchor=tk.CENTER)
        self.save_btn = tk.Button(self, image=self.save_image, width=self.btn_size, height=self.btn_size,
                                     cursor='hand2', relief=tk.FLAT, bg=self.bg_color, activebackground=self.act_color,
                                     overrelief=tk.SUNKEN, anchor=tk.CENTER)
        self.confirm_btn.pack(side=tk.RIGHT,padx=1)
        self.save_btn.pack(side=tk.RIGHT,padx=1)
        self.gif_btn.pack(side=tk.RIGHT,padx=1)
        self.mark_btn.pack(side=tk.RIGHT,padx=1)
        self.undo_btn.pack(side=tk.RIGHT,padx=1)

    def disable_btns(self):
        self.confirm_btn.configure(state='disabled')
        self.save_btn.configure(state='disabled')
        self.gif_btn.configure(state='disabled')
        self.mark_btn.configure(state='disabled')
        self.undo_btn.configure(state='disabled')


    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)

