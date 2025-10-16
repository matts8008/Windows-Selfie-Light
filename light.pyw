import tkinter as tk
import math
import winreg  # for persistent settings on Windows
import ctypes
import ctypes.wintypes

# --- Constants ---
MIN_TEMP = 2700
MAX_TEMP = 6500
REG_PATH = r"Software\SelfieLightApp"

# --- Utility Functions ---

def get_work_area():
    """
    Uses the Windows API to get the primary monitor's work area,
    correctly excluding the taskbar.
    """
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    rect = ctypes.wintypes.RECT()
    # SPI_GETWORKAREA = 0x0030
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    
    x = rect.left
    y = rect.top
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    
    return x, y, width, height

def kelvin_to_rgb(temp_k):
    """Converts a color temperature in Kelvin to an RGB hex string."""
    temp = temp_k / 100.0

    if temp <= 66:
        r = 255
        g = 99.4708025861 * math.log(temp) - 161.1195681661
    else:
        r = 329.698727446 * ((temp - 60) ** -0.1332047592)
        g = 288.1221695283 * ((temp - 60) ** -0.0755148492)
    
    if temp >= 66:
        b = 255
    elif temp <= 19:
        b = 0
    else:
        b = 138.5177312231 * math.log(temp - 10) - 305.0447927307

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def adjust_brightness(hex_color, factor):
    """Adjusts the brightness of a hex color by a given factor."""
    hex_color = hex_color.lstrip("#")
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    rgb = [max(0, min(255, int(c * factor))) for c in rgb]
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def save_setting(name, value):
    """Saves a setting to the Windows Registry."""
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Registry save failed: {e}")

def load_setting(name, default):
    """Loads a setting from the Windows Registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return type(default)(val) # Cast to the same type as the default value
    except Exception:
        return default

# --- Core Classes ---

class LightBar:
    """Represents a single rectangular light bar window."""
    def __init__(self, x, y, w, h, controller, role="generic"):
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.controller = controller
        self.role = role

        self.drag_start = None
        self.resize_edge = None
        self._bind_mouse_events()
        self._create_context_menu()

    def _create_context_menu(self):
        """Creates the right-click context menu."""
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(
            label="Adjust Brightness & Temperature", 
            command=self.controller.popup_adjust
        )

        style_menu = tk.Menu(menu, tearoff=0)
        style_menu.add_command(label="Ring Light", command=lambda: self.controller.set_style("ring"))
        style_menu.add_command(label="Dual Side Bars", command=lambda: self.controller.set_style("sides"))
        style_menu.add_command(label="Thin Border", command=lambda: self.controller.set_style("border"))
        style_menu.add_command(label="Top Bar", command=lambda: self.controller.set_style("top"))
        style_menu.add_command(label="Full Screen", command=lambda: self.controller.set_style("fullscreen"))
        # --- Menu label updated here ---
        menu.add_cascade(label="Light Style", menu=style_menu)

        menu.add_separator()
        menu.add_command(label="Close All", command=self.controller.close_all)

        self.win.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))

    def _bind_mouse_events(self):
        """Binds mouse events for moving and resizing."""
        margin = 10

        def on_motion(event):
            x, y, w, h = event.x, event.y, self.win.winfo_width(), self.win.winfo_height()
            if x < margin or x > w - margin:
                self.win.config(cursor="sb_h_double_arrow")
            elif y < margin or y > h - margin:
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
                self.win.geometry(f"+{x0 + dx}+{y0 + dy}")
            elif self.resize_edge == "left":
                new_w = w0 - dx
                if new_w > 20: self.win.geometry(f"{new_w}x{h0}+{x0 + dx}+{y0}")
            elif self.resize_edge == "right":
                new_w = w0 + dx
                if new_w > 20: self.win.geometry(f"{new_w}x{h0}+{x0}+{y0}")
            elif self.resize_edge == "top":
                new_h = h0 - dy
                if new_h > 20: self.win.geometry(f"{w0}x{new_h}+{x0}+{y0 + dy}")
            elif self.resize_edge == "bottom":
                new_h = h0 + dy
                if new_h > 20: self.win.geometry(f"{w0}x{new_h}+{x0}+{y0}")
            
            if self.role == "border" and self.resize_edge in ("left", "right"):
                self.controller.resize_border(self.win.winfo_width())
            elif self.role == "border" and self.resize_edge in ("top", "bottom"):
                 self.controller.resize_border(self.win.winfo_height())

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

class RingLight:
    """Represents a circular, floating ring light window."""
    def __init__(self, x, y, initial_size, controller):
        self.controller = controller
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        
        # Make the window background transparent
        self.transparent_color = '#abcdef'
        self.win.config(bg=self.transparent_color)
        self.win.attributes('-transparentcolor', self.transparent_color)
        
        self.canvas = tk.Canvas(self.win, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.size = initial_size
        self.win.geometry(f"{self.size}x{self.size}+{x}+{y}")
        
        self.light_color = "#ffffff"
        self.ring_thickness_ratio = 0.3 # Thickness is 30% of the radius
        
        self.drag_start_pos = None
        self.resize_mode = False
        
        self._bind_events()
        self._create_context_menu()
        self.draw_ring()

    def draw_ring(self):
        self.canvas.delete("all")
        center = self.size / 2
        outer_radius = center - 2 # Margin for anti-aliasing issues

        # Draw the light ring and punch a transparent hole in the middle
        self.canvas.create_oval(
            center - outer_radius, center - outer_radius,
            center + outer_radius, center + outer_radius,
            fill=self.light_color, outline="", tags="ring_shape"
        )
        inner_radius = outer_radius * (1 - self.ring_thickness_ratio)
        self.canvas.create_oval(
            center - inner_radius, center - inner_radius,
            center + inner_radius, center + inner_radius,
            fill=self.transparent_color, outline=""
        )

    def _bind_events(self):
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)

    def on_press(self, event):
        if "ring_shape" not in self.canvas.gettags(self.canvas.find_withtag("current")):
            return # Ignore clicks on the transparent part

        center = self.size / 2
        click_dist = math.sqrt((event.x - center)**2 + (event.y - center)**2)
        outer_radius = center - 2
        inner_radius = outer_radius * (1 - self.ring_thickness_ratio)
        
        # Check if click is near an edge for resizing
        edge_margin = 20 
        if abs(click_dist - outer_radius) < edge_margin or abs(click_dist - inner_radius) < edge_margin:
            self.resize_mode = True
        else:
            self.resize_mode = False

        self.drag_start_pos = {
            "x_root": event.x_root, "y_root": event.y_root,
            "win_x": self.win.winfo_x(), "win_y": self.win.winfo_y(),
            "size": self.size
        }

    def on_drag(self, event):
        if not self.drag_start_pos: return

        if self.resize_mode:
            # Resize based on distance from the original center
            center_x = self.drag_start_pos["win_x"] + self.drag_start_pos["size"] / 2
            center_y = self.drag_start_pos["win_y"] + self.drag_start_pos["size"] / 2
            new_radius = math.sqrt((event.x_root - center_x)**2 + (event.y_root - center_y)**2)
            new_size = max(100, int(new_radius * 2)) # Minimum size
            
            new_x = int(center_x - new_size / 2)
            new_y = int(center_y - new_size / 2)
            
            self.size = new_size
            self.win.geometry(f"{self.size}x{self.size}+{new_x}+{new_y}")
            self.draw_ring()
        else:
            # Move the window
            dx = event.x_root - self.drag_start_pos["x_root"]
            dy = event.y_root - self.drag_start_pos["y_root"]
            self.win.geometry(f"+{self.drag_start_pos['win_x'] + dx}+{self.drag_start_pos['win_y'] + dy}")

    def on_release(self, event):
        if self.drag_start_pos: # Save new position and size
            save_setting("RingSize", self.size)
            save_setting("RingX", self.win.winfo_x())
            save_setting("RingY", self.win.winfo_y())
        self.drag_start_pos = None
        self.resize_mode = False
    
    def set_color(self, color):
        self.light_color = color
        self.draw_ring()

    def close(self):
        self.win.destroy()
        
    def _show_context_menu(self, event):
        self._create_context_menu().post(event.x_root, event.y_root)

    def _create_context_menu(self):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Adjust Brightness & Temperature", command=self.controller.popup_adjust)
        style_menu = tk.Menu(menu, tearoff=0)
        style_menu.add_command(label="Ring Light", command=lambda: self.controller.set_style("ring"))
        style_menu.add_command(label="Dual Side Bars", command=lambda: self.controller.set_style("sides"))
        style_menu.add_command(label="Thin Border", command=lambda: self.controller.set_style("border"))
        style_menu.add_command(label="Top Bar", command=lambda: self.controller.set_style("top"))
        style_menu.add_command(label="Full Screen", command=lambda: self.controller.set_style("fullscreen"))
        menu.add_cascade(label="Light Style", menu=style_menu)
        menu.add_separator()
        menu.add_command(label="Close All", command=self.controller.close_all)
        return menu

class Controller:
    """Manages the application state and all light windows."""
    def __init__(self, work_x, work_y, work_w, work_h, root):
        self.work_x, self.work_y = work_x, work_y
        self.work_w, self.work_h = work_w, work_h
        self.root = root
        self.bars = []
        
        # Load persisted settings
        self.color_temp = load_setting("ColorTemp", 4000)
        self.brightness = load_setting("Brightness", 1.0)
        self.style = load_setting("BarStyle", "sides")
        self.border_width = load_setting("BorderWidth", 100)

        self.create_bars()

    def create_bars(self):
        self.close_bars()
        
        if self.style == "ring":
            default_size = 400
            default_x = self.work_x + (self.work_w - default_size) // 2
            default_y = self.work_y + (self.work_h - default_size) // 2
            
            size = load_setting("RingSize", default_size)
            x = load_setting("RingX", default_x)
            y = load_setting("RingY", default_y)
            
            self.bars = [RingLight(x, y, size, self)]
        elif self.style == "sides":
            bw = int(self.work_w * 0.15)
            self.bars = [
                LightBar(self.work_x, self.work_y, bw, self.work_h, self),
                LightBar(self.work_x + self.work_w - bw, self.work_y, bw, self.work_h, self)
            ]
        elif self.style == "border":
            self._create_border_bars(self.border_width)
        elif self.style == "top":
            bar_height = int(self.work_h * 0.2)
            self.bars = [LightBar(self.work_x, self.work_y, self.work_w, bar_height, self)]
        elif self.style == "fullscreen":
            self.bars = [LightBar(self.work_x, self.work_y, self.work_w, self.work_h, self)]
        
        self.update_colors()

    def _create_border_bars(self, thickness):
        self.close_bars()
        bw = max(20, thickness)
        self.bars = [
            LightBar(self.work_x, self.work_y, self.work_w, bw, self, role="border"),
            LightBar(self.work_x, self.work_y + self.work_h - bw, self.work_w, bw, self, role="border"),
            LightBar(self.work_x, self.work_y, bw, self.work_h, self, role="border"),
            LightBar(self.work_x + self.work_w - bw, self.work_y, bw, self.work_h, self, role="border")
        ]
        self.update_colors()

    def set_style(self, style):
        self.style = style
        save_setting("BarStyle", style)
        self.create_bars()

    def update_colors(self):
        base_color = kelvin_to_rgb(self.color_temp)
        final_color = adjust_brightness(base_color, self.brightness)
        for bar in self.bars:
            bar.set_color(final_color)

    def popup_adjust(self):
        win = tk.Toplevel()
        win.title("Adjust Light")
        win.attributes("-topmost", True)
        win.grab_set()
        
        win.update_idletasks()
        win_w, win_h = 320, 180
        x_pos = self.work_x + (self.work_w // 2) - (win_w // 2)
        y_pos = self.work_y + (self.work_h // 2) - (win_h // 2)
        win.geometry(f'{win_w}x{win_h}+{x_pos}+{y_pos}')
        win.resizable(False, False)

        tk.Label(win, text="Color Temperature (K)", pady=5).pack()
        temp_slider = tk.Scale(win, from_=MIN_TEMP, to=MAX_TEMP, orient="horizontal",
                               length=300, resolution=50,
                               command=lambda v: self._update_temp(int(v)))
        temp_slider.set(self.color_temp)
        temp_slider.pack()

        tk.Label(win, text="Brightness", pady=5).pack()
        bright_slider = tk.Scale(win, from_=0.1, to=1.0, orient="horizontal",
                                 length=300, resolution=0.05,
                                 command=lambda v: self._update_brightness(float(v)))
        bright_slider.set(self.brightness)
        bright_slider.pack()

    def _update_temp(self, val):
        self.color_temp = val
        save_setting("ColorTemp", val)
        self.update_colors()

    def _update_brightness(self, val):
        self.brightness = val
        save_setting("Brightness", val)
        self.update_colors()

    def resize_border(self, thickness):
        if self.style != "border": return
        self.border_width = max(20, thickness)
        save_setting("BorderWidth", self.border_width)
        self._create_border_bars(self.border_width)

    def close_bars(self):
        for bar in self.bars:
            bar.close()
        self.bars = []

    def close_all(self):
        self.close_bars()
        self.root.quit()

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw() # Hide the main root window

    work_area_x, work_area_y, work_area_width, work_area_height = get_work_area()

    app_controller = Controller(
        work_x=work_area_x,
        work_y=work_area_y,
        work_w=work_area_width,
        work_h=work_area_height,
        root=root
    )

    root.mainloop()
