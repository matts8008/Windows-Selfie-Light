import tkinter as tk
import screeninfo
import math

MIN_TEMP = 2700
MAX_TEMP = 6500

def kelvin_to_rgb(temp_k):
    temp = temp_k / 100.0

    if temp <= 66:
        r = 255
    else:
        r = 329.698727446 * ((temp - 60) ** -0.1332047592)
        r = max(0, min(255, r))

    if temp <= 66:
        g = 99.4708025861 * math.log(temp) - 161.1195681661
        g = max(0, min(255, g))
    else:
        g = 288.1221695283 * ((temp - 60) ** -0.0755148492)
        g = max(0, min(255, g))

    if temp >= 66:
        b = 255
    elif temp <= 19:
        b = 0
    else:
        b = 138.5177312231 * math.log(temp - 10) - 305.0447927307
        b = max(0, min(255, b))

    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def adjust_brightness(hex_color, factor):
    hex_color = hex_color.lstrip("#")
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    rgb = [max(0, min(255, int(c * factor))) for c in rgb]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

class LightBar:
    instances = []

    def __init__(self, x, y, w, h, controller, role="generic"):
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.controller = controller
        self.role = role

        self.drag_start = None
        self.resize_edge = None
        self._bind_mouse()

        # Right-click menu
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Color Temperature", command=self.controller.popup_temp)
        menu.add_command(label="Brightness", command=self.controller.popup_brightness)

        style_menu = tk.Menu(menu, tearoff=0)
        style_menu.add_command(label="Dual Side Bars", command=lambda: self.controller.set_style("sides"))
        style_menu.add_command(label="Thin Border", command=lambda: self.controller.set_style("border"))
        style_menu.add_command(label="Top Bar", command=lambda: self.controller.set_style("top"))
        style_menu.add_command(label="Full Screen", command=lambda: self.controller.set_style("fullscreen"))
        menu.add_cascade(label="Bar Style", menu=style_menu)

        menu.add_separator()
        menu.add_command(label="Close All", command=self.controller.close_all)

        self.win.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))
        LightBar.instances.append(self)

    def _bind_mouse(self):
        margin = 10

        def on_motion(event):
            x, y, w, h = event.x, event.y, self.win.winfo_width(), self.win.winfo_height()
            if x < margin:
                self.win.config(cursor="sb_h_double_arrow")
            elif x > w - margin:
                self.win.config(cursor="sb_h_double_arrow")
            elif y < margin:
                self.win.config(cursor="sb_v_double_arrow")
            elif y > h - margin:
                self.win.config(cursor="sb_v_double_arrow")
            else:
                self.win.config(cursor="arrow")

        def on_press(event):
            self.drag_start = (event.x_root, event.y_root,
                               self.win.winfo_x(), self.win.winfo_y(),
                               self.win.winfo_width(), self.win.winfo_height())
            x, y, w, h = event.x, event.y, self.win.winfo_width(), self.win.winfo_height()
            if x < margin: self.resize_edge = "left"
            elif x > w - margin: self.resize_edge = "right"
            elif y < margin: self.resize_edge = "top"
            elif y > h - margin: self.resize_edge = "bottom"
            else: self.resize_edge = "move"

        def on_drag(event):
            if not self.drag_start: return
            dx = event.x_root - self.drag_start[0]
            dy = event.y_root - self.drag_start[1]
            x0, y0, w0, h0 = self.drag_start[2:]

            if self.resize_edge == "move":
                self.win.geometry(f"+{x0+dx}+{y0+dy}")
            elif self.resize_edge == "left":
                new_w = w0 - dx
                if new_w > 20:
                    self.win.geometry(f"{new_w}x{h0}+{x0+dx}+{y0}")
                    if self.role == "border":
                        self.controller.resize_border(new_w)
            elif self.resize_edge == "right":
                new_w = w0 + dx
                if new_w > 20:
                    self.win.geometry(f"{new_w}x{h0}+{x0}+{y0}")
                    if self.role == "border":
                        self.controller.resize_border(new_w)
            elif self.resize_edge == "top":
                new_h = h0 - dy
                if new_h > 20:
                    self.win.geometry(f"{w0}x{new_h}+{x0}+{y0+dy}")
                    if self.role == "border":
                        self.controller.resize_border(new_h, vertical=True)
            elif self.resize_edge == "bottom":
                new_h = h0 + dy
                if new_h > 20:
                    self.win.geometry(f"{w0}x{new_h}+{x0}+{y0}")
                    if self.role == "border":
                        self.controller.resize_border(new_h, vertical=True)

        def on_release(event):
            self.drag_start = None
            self.resize_edge = None

        self.win.bind("<Motion>", on_motion)
        self.win.bind("<Button-1>", on_press)
        self.win.bind("<B1-Motion>", on_drag)
        self.win.bind("<ButtonRelease-1>", on_release)

    def set_color(self, color):
        self.win.configure(bg=color)

    def close(self):
        self.win.destroy()

class Controller:
    def __init__(self, screen_w, screen_h, work_h, root):
        self.screen_w, self.screen_h = screen_w, work_h  # use working height (no taskbar)
        self.brightness = 1.0
        self.color_temp = 4000
        self.bars = []
        self.style = "sides"
        self.root = root
        self.create_bars()

    def create_bars(self):
        self.close_bars()
        if self.style == "sides":
            bw = int(self.screen_w * 0.15)
            self.bars = [
                LightBar(0, 0, bw, self.screen_h, self, role="left"),
                LightBar(self.screen_w - bw, 0, bw, self.screen_h, self, role="right")
            ]
        elif self.style == "border":
            bw = 100
            self.bars = [
                LightBar(0, 0, self.screen_w, bw, self, role="border"),
                LightBar(0, self.screen_h-bw, self.screen_w, bw, self, role="border"),
                LightBar(0, 0, bw, self.screen_h, self, role="border"),
                LightBar(self.screen_w-bw, 0, bw, self.screen_h, self, role="border")
            ]
        elif self.style == "top":
            self.bars = [LightBar(0, 0, self.screen_w, 150, self, role="top")]
        elif self.style == "fullscreen":
            self.bars = [LightBar(0, 0, self.screen_w, self.screen_h, self, role="fullscreen")]
        self.update_colors()

    def set_style(self, style):
        self.style = style
        self.create_bars()

    def update_colors(self):
        base = kelvin_to_rgb(self.color_temp)
        col = adjust_brightness(base, self.brightness)
        for b in self.bars:
            b.set_color(col)

    def popup_temp(self):
        win = tk.Toplevel()
        win.title("Color Temperature")
        win.attributes("-topmost", True)
        win.grab_set()
        tk.Label(win, text="Temperature (K)").pack()
        slider = tk.Scale(win, from_=MIN_TEMP, to=MAX_TEMP, orient="horizontal",
                          length=300, resolution=100,
                          command=lambda v: self._update_temp(int(v)))
        slider.set(self.color_temp)
        slider.pack()

    def popup_brightness(self):
        win = tk.Toplevel()
        win.title("Brightness")
        win.attributes("-topmost", True)
        win.grab_set()
        tk.Label(win, text="Brightness").pack()
        slider = tk.Scale(win, from_=0.1, to=1.0, orient="horizontal",
                          length=300, resolution=0.05,
                          command=lambda v: self._update_brightness(float(v)))
        slider.set(self.brightness)
        slider.pack()

    def _update_temp(self, val):
        self.color_temp = val
        self.update_colors()

    def _update_brightness(self, val):
        self.brightness = val
        self.update_colors()

    def resize_border(self, thickness, vertical=False):
        if self.style != "border":
            return
        self.close_bars()
        bw = max(20, thickness)
        self.bars = [
            LightBar(0, 0, self.screen_w, bw, self, role="border"),
            LightBar(0, self.screen_h-bw, self.screen_w, bw, self, role="border"),
            LightBar(0, 0, bw, self.screen_h, self, role="border"),
            LightBar(self.screen_w-bw, 0, bw, self.screen_h, self, role="border")
        ]
        self.update_colors()

    def close_bars(self):
        for b in self.bars:
            b.close()
        self.bars = []

    def close_all(self):
        for b in LightBar.instances:
            try: b.close()
            except: pass
        self.root.quit()

# ---- Main ----
if __name__ == "__main__":
    screen = screeninfo.get_monitors()[0]
    root = tk.Tk()
    root.withdraw()

    # taskbar height = difference between monitor height and tk screen height
    total_h = screen.height
    work_h = root.winfo_screenheight()  # excludes taskbar
    controller = Controller(screen.width, total_h, work_h, root)
    root.mainloop()
