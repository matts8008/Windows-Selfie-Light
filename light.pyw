import tkinter as tk
import screeninfo
import math

# Range for realistic color temps
MIN_TEMP = 2700
MAX_TEMP = 6500

def kelvin_to_rgb(temp_k):
    """Convert Kelvin color temperature to approximate RGB."""
    temp = temp_k / 100.0

    if temp <= 66:
        r = 255
    else:
        r = temp - 60
        r = 329.698727446 * (r ** -0.1332047592)
        r = max(0, min(255, r))

    if temp <= 66:
        g = 99.4708025861 * math.log(temp) - 161.1195681661
        g = max(0, min(255, g))
    else:
        g = temp - 60
        g = 288.1221695283 * (g ** -0.0755148492)
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
    """Apply brightness factor to hex color."""
    hex_color = hex_color.lstrip("#")
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    rgb = [max(0, min(255, int(c * factor))) for c in rgb]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

class LightBar:
    instances = []

    def __init__(self, x, y, w, h, controller):
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.controller = controller

        self.x = self.y = 0
        self._bind_drag()

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

    def _bind_drag(self):
        def start_move(e):
            self.x, self.y = e.x, e.y
        def do_move(e):
            dx, dy = e.x - self.x, e.y - self.y
            new_x = self.win.winfo_x() + dx
            new_y = self.win.winfo_y() + dy
            self.win.geometry(f"+{new_x}+{new_y}")
        self.win.bind("<Button-1>", start_move)
        self.win.bind("<B1-Motion>", do_move)

    def set_color(self, color):
        self.win.configure(bg=color)

    def close(self):
        self.win.destroy()

class Controller:
    def __init__(self, screen_w, screen_h, root):
        self.screen_w, self.screen_h = screen_w, screen_h
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
                LightBar(0, 0, bw, self.screen_h, self),
                LightBar(self.screen_w - bw, 0, bw, self.screen_h, self)
            ]
        elif self.style == "border":
            bw = 100
            self.bars = [
                LightBar(0, 0, self.screen_w, bw, self),
                LightBar(0, self.screen_h-bw, self.screen_w, bw, self),
                LightBar(0, 0, bw, self.screen_h, self),
                LightBar(self.screen_w-bw, 0, bw, self.screen_h, self)
            ]
        elif self.style == "top":
            self.bars = [LightBar(0, 0, self.screen_w, 150, self)]
        elif self.style == "fullscreen":
            self.bars = [LightBar(0, 0, self.screen_w, self.screen_h, self)]
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
        win.attributes("-topmost", True)   # keep above bars
        win.grab_set()                     # focus this popup
        tk.Label(win, text="Temperature (K)").pack()
        slider = tk.Scale(win, from_=MIN_TEMP, to=MAX_TEMP, orient="horizontal",
                          length=300, resolution=100,
                          command=lambda v: self._update_temp(int(v)))
        slider.set(self.color_temp)
        slider.pack()

    def popup_brightness(self):
        win = tk.Toplevel()
        win.title("Brightness")
        win.attributes("-topmost", True)   # keep above bars
        win.grab_set()                     # focus this popup
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
    root.withdraw()  # hide root
    controller = Controller(screen.width, screen.height, root)
    root.mainloop()
