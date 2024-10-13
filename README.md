# MigicC  — A tool for screenshot

2024-10-13 update version bate 0.2 - add README.md and fix bugs

1. add a README.md file.

2. fix bug: shortcut key can not changed correctly. 

   file position：mainwin.py 

   row 42: .replace('Key,', '') change to .replace('Key.', '')

   row 52: key.char change to keyname

3. fix bug:  screenshot is darker than the actual.

   file position : shortcut.py

   row 88: add

   ```
   image = ImageEnhance.Brightness(image).enhance(1.33)
   ```

4. fix bug: screenshot has border.

   file position : shortcut.py

   row 232-235.

   ```python
   rightx, righty = max(self.startx, event.x), max(self.starty, event.y)
   self.shortcut_area = [(leftx + 1, lefty + 1),(rightx - 1, righty - 1)]
   image = Image.new('RGBA',(rightx-leftx,righty-lefty), (255, 255, 255, 0))
   self.rec_image = ImageTk.PhotoImage(ImageOps.expand(image, border=2, fill='#0378C1'))
   self.canvas.create_image(leftx, lefty, image=self.rec_image, anchor=tk.NW, tags='shortcut_area')
   
   ```

   change to

   ```python
   rightx, righty = max(self.startx, event.x), max(self.starty, event.y)
   self.shortcut_area = [(leftx, lefty),(rightx, righty)]
   image = Image.new('RGBA',(rightx - leftx, righty - lefty), (255, 255, 255, 0))
   self.rec_image = ImageTk.PhotoImage(ImageOps.expand(image, border=1, fill='#0378C1'))
   self.canvas.create_image(leftx-1, lefty-1, image=self.rec_image, anchor=tk.NW, tags='shortcut_area')
   ```

5. fix bug:  GIF only shows the first image.

   file position : gifwin.py

​	row 92:

```python
im.save(ask, save_all=True, append_iamges=img_list[1:], loop=0, duration=dur)
```

​	change to

```python
im.save(ask, save_all=True, append_images=img_list[1:], loop=0, duration=dur)
```

------





# How to use

![image-20241013082815869](pics/image-20241013082815869.png)

##### 1. ![image-20241013083300756](pics\image-20241013083300756.png)  the button to start screenshot. And right click to exit screenshot mode.



![aaa](pics\01.gif)

###### 1.1![image-20241013094450320](pics\image-20241013094450320.png) toolbar.

![image-20241013094527388](pics\image-20241013094527388.png)undo mark

![image-20241013094617793](pics\image-20241013094617793.png)mark rectangle

![image-20241013094700085](pics\image-20241013094700085.png)recording gif

![image-20241013094911704](pics\image-20241013094911704.png)save screenshot

![image-20241013094936350](pics\image-20241013094936350.png)save to clipboard

![1](pics\02.gif)

![12](pics\03.gif)



##### 2. ![image-20241013095753554](pics\image-20241013095753554.png)the button to get the same location as the previous screenshot. And you can choose to save mode or clipboard mode.



![13](pics\04.gif)



you can choose to save mode or clipboard mode at here.

![14](pics\05.gif)



3. ##### Shortcut Key. The above two buttons can be triggered by shortcut keys.

   ![image-20241013101057964](pics\image-20241013101057964.png)

you can change it to your preference

![15](pics\06.gif)

