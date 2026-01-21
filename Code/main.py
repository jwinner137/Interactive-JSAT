# main.py
import tkinter as tk
from app import GraphBuilderApp

if __name__ == "__main__":
    root = tk.Tk()
    app = GraphBuilderApp(root)
    root.mainloop()