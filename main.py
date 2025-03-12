import tkinter as tk
from gui import NetworkToolApp

if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkToolApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
