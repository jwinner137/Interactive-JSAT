import tkinter as tk
from tkinter import simpledialog, messagebox, Toplevel, filedialog, ttk
import networkx as nx
import math
import json

# ==========================================
# === SUB-SYSTEM: INTERACTIVE PANEL ===
# ==========================================
class InteractiveComparisonPanel:
    def __init__(self, parent, graph, name, node_radius, agents_map, redraw_callback, click_callback):
        self.G = graph
        self.name = name
        self.node_radius = node_radius
        self.agents = agents_map
        self.redraw_callback = redraw_callback 
        self.click_callback = click_callback   

        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_mode = None 
        self.drag_data = None 
        self.initialized = False

        self.outer = tk.Frame(parent, bd=2, relief=tk.GROOVE)
        self.outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(self.outer, text=name, font=("Arial", 11, "bold"), bg="#ddd").pack(fill=tk.X)
        self.canvas = tk.Canvas(self.outer, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<MouseWheel>", self.on_zoom)      
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(e, 1))  
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(e, -1)) 
        
        self.canvas.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        if not self.initialized:
            self.center_view(event.width, event.height)
            self.initialized = True
        self.redraw()

    def center_view(self, width, height):
        if self.G.number_of_nodes() == 0: return
        xs = [d.get('pos', (0,0))[0] for n, d in self.G.nodes(data=True)]
        ys = [d.get('pos', (0,0))[1] for n, d in self.G.nodes(data=True)]
        if not xs: return
        
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        graph_cx = (min_x + max_x) / 2
        graph_cy = (min_y + max_y) / 2
        
        self.offset_x = (width / 2) - (graph_cx * self.zoom)
        self.offset_y = (height / 2) - (graph_cy * self.zoom)

    def to_screen(self, wx, wy):
        sx = (wx * self.zoom) + self.offset_x
        sy = (wy * self.zoom) + self.offset_y
        return sx, sy

    def to_world(self, sx, sy):
        wx = (sx - self.offset_x) / self.zoom
        wy = (sy - self.offset_y) / self.zoom
        return wx, wy

    def redraw(self):
        self.canvas.delete("all")
        r = self.node_radius * self.zoom 
        
        # Edges
        for u, v in self.G.edges():
            p1 = self.G.nodes[u].get('pos', (0,0))
            p2 = self.G.nodes[v].get('pos', (0,0))
            sx1, sy1 = self.to_screen(p1[0], p1[1])
            sx2, sy2 = self.to_screen(p2[0], p2[1])
            dx, dy = sx2-sx1, sy2-sy1
            dist = math.hypot(dx, dy)
            if dist == 0: continue
            gap = r + 2
            tx = sx2 - (dx/dist)*gap
            ty = sy2 - (dy/dist)*gap
            self.canvas.create_line(sx1, sy1, tx, ty, arrow=tk.LAST, width=2*self.zoom)

        # Nodes
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            
            ag = d.get('agent', "Unassigned")
            fill = self.agents.get(ag, "white")
            if '_color_cache' in d: fill = d['_color_cache']

            if d.get('type') == "Function":
                self.canvas.create_rectangle(sx-r, sy-r, sx+r, sy+r, fill=fill, outline="black")
            else:
                # FIXED TYPO HERE: Changed 'y-r' to 'sy-r'
                self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=fill, outline="black")
            
            lbl = d.get('label', '')
            font_size = max(8, int(10 * self.zoom))
            self.canvas.create_text(sx, sy, text=lbl, font=("Arial", font_size, "bold"))

    def on_zoom(self, event, direction=None):
        if direction is None:
            if event.delta > 0: factor = 1.1
            else: factor = 0.9
        else:
            if direction > 0: factor = 1.1
            else: factor = 0.9
        self.zoom *= factor
        self.redraw()

    def on_mouse_down(self, event):
        mx, my = event.x, event.y
        clicked_node = None
        r_screen = self.node_radius * self.zoom
        for n, d in self.G.nodes(data=True):
            wx, wy = d.get('pos', (0,0))
            sx, sy = self.to_screen(wx, wy)
            if math.hypot(mx-sx, my-sy) <= r_screen:
                clicked_node = n; break
        
        if clicked_node is not None:
            self.drag_mode = "NODE"; self.drag_data = clicked_node
            label = self.G.nodes[clicked_node].get('label', '')
            if self.click_callback: self.click_callback(label)
        else:
            self.drag_mode = "PAN"; self.drag_data = (mx, my)

    def on_mouse_drag(self, event):
        if self.drag_node is not None:
            # Check if drag threshold is passed
            if math.hypot(event.x - self.drag_start_pos[0], event.y - self.drag_start_pos[1]) > 5: 
                self.is_dragging = True
                
                # UPDATE: Always update (x, y) to mouse position during drag
                # This allows visual dragging across layers in JSAT mode
                self.G.nodes[self.drag_node]['pos'] = (event.x, event.y)
                
                self.redraw()

    def on_mouse_up(self, event):
        if self.drag_node is not None:
            if self.is_dragging: 
                # Save undo state
                self.undo_stack.append(self.pre_drag_graph_state)
                if len(self.undo_stack) > self.history_limit: self.undo_stack.pop(0)
                self.redo_stack.clear()
                
                # SNAP LOGIC: If in JSAT mode, snap to the nearest layer
                if self.view_mode == "JSAT":
                    new_layer = self.get_layer_from_y(event.y)
                    if new_layer:
                        # 1. Update the node's assigned layer
                        self.G.nodes[self.drag_node]['layer'] = new_layer
                        # 2. Snap the position to that layer's Y-coordinate
                        self.G.nodes[self.drag_node]['pos'] = (event.x, self.jsat_layers[new_layer])
                        self.redraw()
                        
            else: 
                # It was just a click, not a drag
                self.handle_click(self.drag_node)
            
            self.drag_node = None
            self.is_dragging = False


# ==========================================
# === MAIN APPLICATION ===
# ==========================================

class GraphBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("System Architect v11.6: Fixed Resources")
        self.root.geometry("1400x900") 
        
        # --- Backend Data ---
        self.G = nx.DiGraph()
        self.node_radius = 20
        self.saved_archs = {} 
        self.undo_stack = []
        self.redo_stack = []
        self.history_limit = 6
        
        self.selected_node = None     
        self.inspected_node = None    
        self.drag_node = None      
        self.drag_start_pos = None 
        self.is_dragging = False   
        self.pre_drag_graph_state = None
        
        self.mode = "SELECT"          
        self.agents = {"Unassigned": "white"}
        self.current_agent = "Unassigned"
        
        # View & Layers
        self.view_mode = "FREE"
        self.jsat_layers = {
            "Synchronicity Functions": 100,
            "Coordination Grounding": 250,
            "Distributed Work": 400,
            "Base Environment": 550
        }
        self.layer_order = [
            "Synchronicity Functions", 
            "Coordination Grounding", 
            "Distributed Work", 
            "Base Environment"
        ]
        
        self.sidebar_drag_data = None
        
        self.setup_ui()
        
    def setup_ui(self):
        toolbar_frame = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.build_toolbar(toolbar_frame)

        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_container, bg="white")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # --- DASHBOARD SIDEBAR ---
        self.dashboard_frame = tk.Frame(main_container, width=350, bg="#f0f0f0", bd=1, relief=tk.SUNKEN)
        self.dashboard_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.dashboard_frame.pack_propagate(False) 
        
        tk.Label(self.dashboard_frame, text="Network Dashboard", font=("Arial", 14, "bold"), bg="#4a4a4a", fg="white", pady=8).pack(fill=tk.X)
        
        # Fixed Inspector (Top)
        self.inspector_frame = tk.Frame(self.dashboard_frame, bg="#fff8e1", bd=2, relief=tk.GROOVE)
        self.inspector_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Scrollable Area (Bottom)
        self.scroll_canvas = tk.Canvas(self.dashboard_frame, bg="#f0f0f0")
        self.scrollbar = tk.Scrollbar(self.dashboard_frame, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollable_content = tk.Frame(self.scroll_canvas, bg="#f0f0f0")

        self.scroll_canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw", width=330)
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollable_content.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

        self.status_label = tk.Label(self.root, text="Mode: Select & Inspect", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.redraw()

    def build_toolbar(self, parent):
        r1 = tk.Frame(parent)
        r1.pack(fill=tk.X, pady=2)
        tk.Button(r1, text="↶", command=self.undo, width=2).pack(side=tk.LEFT, padx=1)
        tk.Button(r1, text="↷", command=self.redo, width=2).pack(side=tk.LEFT, padx=1)
        tk.Frame(r1, width=10).pack(side=tk.LEFT)
        
        self.view_btn = tk.Button(r1, text="👁 View: Free", command=self.toggle_view, bg="#e1bee7", font=("Arial", 9, "bold"))
        self.view_btn.pack(side=tk.LEFT, padx=10)
        
        tk.Button(r1, text="➤ Select", command=lambda: self.set_mode("SELECT"), bg="#d0f0c0").pack(side=tk.LEFT, padx=2)
        tk.Button(r1, text="Add Func", command=lambda: self.set_mode("ADD_FUNC")).pack(side=tk.LEFT, padx=2)
        tk.Button(r1, text="Add Res", command=lambda: self.set_mode("ADD_RES")).pack(side=tk.LEFT, padx=2)
        tk.Button(r1, text="Connect", command=lambda: self.set_mode("ADD_EDGE")).pack(side=tk.LEFT, padx=2)
        tk.Button(r1, text="Delete", command=lambda: self.set_mode("DELETE"), bg="#ffcccc", fg="red").pack(side=tk.LEFT, padx=5)
        
        r2 = tk.Frame(parent)
        r2.pack(fill=tk.X, pady=2)
        tk.Label(r2, text="| RAM:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Store", command=self.save_architecture_internal).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="COMPARE", command=self.open_comparison_dialog, bg="#ffd700", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        tk.Label(r2, text="| Disk:", fg="#888").pack(side=tk.LEFT, padx=5)
        tk.Button(r2, text="Save JSON", command=self.initiate_save_json).pack(side=tk.LEFT, padx=2)
        tk.Button(r2, text="Open JSON", command=self.load_from_json).pack(side=tk.LEFT, padx=2)

    # =========================================
    # === JSAT LAYER LOGIC ===
    # =========================================

    def toggle_view(self):
        if self.view_mode == "FREE":
            self.view_mode = "JSAT"
            self.view_btn.config(text="👁 View: JSAT Layers")
        else:
            self.view_mode = "FREE"
            self.view_btn.config(text="👁 View: Free")
        self.redraw()

    def get_node_layer(self, node_data):
        if 'layer' in node_data and node_data['layer'] in self.jsat_layers: return node_data['layer']
        lbl, typ = node_data.get('label', ''), node_data.get('type', '')
        if lbl.startswith("Confirming"): return "Synchronicity Functions"
        if lbl.startswith("Confirmation"): return "Coordination Grounding"
        return "Distributed Work" if typ == "Function" else "Base Environment"

    def get_layer_from_y(self, y):
        closest_layer = None
        min_dist = 9999
        for name, ly in self.jsat_layers.items():
            dist = abs(y - ly)
            if dist < min_dist:
                min_dist = dist
                closest_layer = name
        return closest_layer

    def get_draw_pos(self, node_id):
        data = self.G.nodes[node_id]
        raw_x, raw_y = data.get('pos', (100, 100))
        if self.view_mode == "JSAT" and self.drag_node == node_id and self.is_dragging:
            return raw_x, raw_y
        if self.view_mode == "FREE":
            return raw_x, raw_y
        else:
            return raw_x, self.jsat_layers[self.get_node_layer(data)]

    def redraw(self):
        self.canvas.delete("all")
        if self.view_mode == "JSAT":
            w = self.canvas.winfo_width()
            for layer_name in self.layer_order:
                y = self.jsat_layers[layer_name]
                self.canvas.create_line(0, y, 2000, y, fill="#ddd", dash=(4, 4))
                self.canvas.create_text(10, y-10, text=layer_name, anchor="w", fill="#888", font=("Arial", 8, "italic"))

        r = self.node_radius
        for u, v in self.G.edges():
            p1 = self.get_draw_pos(u); p2 = self.get_draw_pos(v)
            dx, dy = p2[0]-p1[0], p2[1]-p1[1]
            dist = math.hypot(dx, dy)
            if dist == 0: continue
            gap = r + 2
            tx = p2[0] - (dx/dist)*gap
            ty = p2[1] - (dy/dist)*gap
            self.canvas.create_line(p1[0], p1[1], tx, ty, arrow=tk.LAST, width=2)
            
        for n, d in self.G.nodes(data=True):
            x, y = self.get_draw_pos(n)
            fill = self.agents.get(d.get('agent'), "white")
            outline = "blue" if n == self.selected_node else "orange" if n == self.inspected_node else "black"
            width = 3 if outline != "black" else 1
            if d.get('type') == "Function":
                self.canvas.create_rectangle(x-r, y-r, x+r, y+r, fill=fill, outline=outline, width=width)
            else:
                self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=fill, outline=outline, width=width)
            self.canvas.create_text(x, y, text=d.get('label',''), font=("Arial", 10, "bold"))
            
        self.rebuild_dashboard()

    # =========================================
    # === SIDEBAR DRAG-AND-DROP LOGIC ===
    # =========================================
    
    def on_sidebar_node_press(self, event, node_id):
        self.sidebar_drag_data = node_id
        self.root.config(cursor="hand2") 

    def on_sidebar_node_release(self, event):
        self.root.config(cursor="")
        if self.sidebar_drag_data is None: return
        
        target_widget = self.root.winfo_containing(event.x_root, event.y_root)
        found_agent = None
        curr = target_widget
        while curr:
            if hasattr(curr, "agent_name"):
                found_agent = curr.agent_name
                break
            curr = curr.master
            if curr == self.root: break
            
        if found_agent:
            self.save_state()
            self.assign_agent_logic(self.sidebar_drag_data, found_agent)
            self.redraw()
        
        self.sidebar_drag_data = None

    # =========================================
    # === REBUILD DASHBOARD ===
    # =========================================

    def rebuild_dashboard(self):
        # 1. Inspector
        for w in self.inspector_frame.winfo_children(): w.destroy()
        if self.inspected_node is not None and self.G.has_node(self.inspected_node):
            d = self.G.nodes[self.inspected_node]
            tk.Label(self.inspector_frame, text="SELECTED NODE INSPECTOR", bg="#fff8e1", font=("Arial", 10, "bold")).pack(pady=2)
            
            r1 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r1.pack(fill=tk.X, padx=5)
            tk.Label(r1, text=f"ID: {self.inspected_node} | Lbl: {d.get('label')}", bg="#fff8e1", font=("Arial", 9, "bold")).pack(anchor="w")
            
            r2 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r2.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(r2, text="Layer:", bg="#fff8e1").pack(side=tk.LEFT)
            current_layer = self.get_node_layer(d)
            layer_var = tk.StringVar(value=current_layer)
            layer_box = ttk.Combobox(r2, textvariable=layer_var, values=self.layer_order, state="readonly", width=22)
            layer_box.pack(side=tk.LEFT, padx=5)
            def on_layer_change(event):
                self.save_state(); self.G.nodes[self.inspected_node]['layer'] = layer_var.get(); self.redraw()
            layer_box.bind("<<ComboboxSelected>>", on_layer_change)

            r3 = tk.Frame(self.inspector_frame, bg="#fff8e1"); r3.pack(fill=tk.X, padx=5, pady=5)
            try: bet = nx.betweenness_centrality(self.G)[self.inspected_node]
            except: bet = 0.0
            try: clo = nx.closeness_centrality(self.G)[self.inspected_node]
            except: clo = 0.0
            try: eig = nx.eigenvector_centrality(self.G, max_iter=1000).get(self.inspected_node, 0)
            except: eig = 0.0
            try: deg_cent = nx.degree_centrality(self.G)[self.inspected_node]
            except: deg_cent = 0.0
            stat_txt = (f"Degree Cent: {deg_cent:.3f}\nBetweenness: {bet:.3f}\nCloseness:   {clo:.3f}\nEigenvector: {eig:.3f}")
            tk.Label(r3, text=stat_txt, bg="#fff8e1", justify=tk.LEFT, font=("Consolas", 9)).pack(anchor="w")
        else:
            tk.Label(self.inspector_frame, text="(Select a node to inspect)", bg="#fff8e1", fg="#888").pack(pady=5)

        # 2. Scrollable Section
        for w in self.scrollable_content.winfo_children(): w.destroy()
        
        # --- GLOBAL STATS ---
        tk.Label(self.scrollable_content, text="Network Statistics", font=("Arial", 11, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(10, 5))
        stats_frame = tk.Frame(self.scrollable_content, bg="white", bd=1, relief=tk.SOLID); stats_frame.pack(fill=tk.X, padx=5)
        try: dens = nx.density(self.G)
        except: dens = 0
        try: clust = nx.average_clustering(self.G.to_undirected()) 
        except: clust = 0
        tk.Label(stats_frame, text=f"Nodes: {self.G.number_of_nodes()} | Edges: {self.G.number_of_edges()}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Density: {dens:.3f}", bg="white").pack(anchor="w", padx=5)
        tk.Label(stats_frame, text=f"Avg Clustering: {clust:.3f}", bg="white").pack(anchor="w", padx=5)

        # --- AGENT OVERVIEW & CONTROLS ---
        tk.Label(self.scrollable_content, text="Agent Overview", font=("Arial", 11, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(15, 2))
        
        # CONTROLS
        ctrl_frame = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(ctrl_frame, text="New Agent", command=self.create_agent, bg="white").pack(side=tk.LEFT, padx=2, pady=2)
        
        self.agent_frame = tk.Frame(ctrl_frame); self.agent_frame.pack(side=tk.LEFT, padx=2)
        self.agent_var = tk.StringVar(value=self.current_agent)
        self.agent_menu = tk.OptionMenu(self.agent_frame, self.agent_var, *self.agents.keys(), command=self.select_agent)
        self.agent_menu.pack(side=tk.LEFT)
        
        tk.Button(ctrl_frame, text="Assign Mode", command=lambda: self.set_mode("ASSIGN_AGENT"), bg="white").pack(side=tk.LEFT, padx=2)

        # AGENT LISTS
        agent_map = {name: [] for name in self.agents.keys()}
        for node, data in self.G.nodes(data=True):
            ag = data.get('agent', 'Unassigned')
            if ag in agent_map: agent_map[ag].append(node)
            else: agent_map.setdefault(ag, []).append(node)

        for agent_name, color in self.agents.items():
            af = tk.Frame(self.scrollable_content, bg="#e0e0e0", bd=1, relief=tk.RAISED)
            af.pack(fill=tk.X, pady=2, padx=5)
            af.agent_name = agent_name 
            
            hf = tk.Frame(af, bg="#e0e0e0"); hf.pack(fill=tk.X)
            hf.agent_name = agent_name
            
            cb = tk.Label(hf, bg=color, width=3); cb.pack(side=tk.LEFT, padx=5)
            cb.bind("<Button-1>", lambda e, a=agent_name: self.edit_agent(a))
            cb.agent_name = agent_name
            
            lbl = tk.Label(hf, text=agent_name, bg="#e0e0e0", font=("Arial", 10, "bold"))
            lbl.pack(side=tk.LEFT, fill=tk.X)
            lbl.bind("<Button-1>", lambda e, a=agent_name: self.edit_agent(a))
            lbl.agent_name = agent_name

            nodes_list = agent_map.get(agent_name, [])
            if nodes_list:
                for nid in nodes_list:
                    nlbl = self.G.nodes[nid].get('label', str(nid))
                    btn = tk.Button(af, text=f"• {nlbl}", anchor="w", bg="white", relief=tk.FLAT, font=("Arial", 9),
                              command=lambda n=nid: self.handle_click(n))
                    btn.pack(fill=tk.X, padx=10, pady=1)
                    btn.bind("<Button-1>", lambda e, n=nid: self.on_sidebar_node_press(e, n))
                    btn.bind("<B1-Motion>", lambda e: None)
                    btn.bind("<ButtonRelease-1>", self.on_sidebar_node_release)
            else:
                l = tk.Label(af, text="(Empty)", bg="#e0e0e0", fg="#666", font=("Arial", 8, "italic"))
                l.pack(anchor="w", padx=10); l.agent_name = agent_name

        # Layer Breakdown
        # --- LAYER BREAKDOWN (Only in JSAT View) ---
        if self.view_mode == "JSAT":
            tk.Label(self.scrollable_content, text="Layer Breakdown", font=("Arial", 11, "bold"), bg="#f0f0f0").pack(fill=tk.X, pady=(15, 2))
            
            # Map nodes to layers
            layer_map = {l: [] for l in self.layer_order}
            for n, d in self.G.nodes(data=True):
                lname = self.get_node_layer(d)
                if lname in layer_map: layer_map[lname].append(n)
            
            for lname in self.layer_order:
                lf = tk.Frame(self.scrollable_content, bg="white", bd=1, relief=tk.SOLID)
                lf.pack(fill=tk.X, padx=5, pady=2)
                
                # --- CHANGE IS HERE: Added count to the label text ---
                lnodes = layer_map[lname]
                count = len(lnodes)
                header_text = f"{lname}: {count} nodes"
                
                tk.Label(lf, text=header_text, bg="#ddd", font=("Arial", 9, "bold")).pack(fill=tk.X)
                
                if lnodes:
                    for nid in lnodes:
                        nlbl = self.G.nodes[nid].get('label', str(nid))
                        ag = self.G.nodes[nid].get('agent', 'Unassigned')
                        col = self.agents.get(ag, "white")
                        
                        row = tk.Frame(lf, bg="white"); row.pack(fill=tk.X, padx=5, pady=1)
                        tk.Label(row, bg=col, width=1, height=1).pack(side=tk.LEFT)
                        tk.Label(row, text=nlbl, bg="white", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)
                else:
                    tk.Label(lf, text="(No nodes)", bg="white", fg="#888", font=("Arial", 8, "italic")).pack(padx=5)

    # =========================================
    # === INTERACTIONS (Mouse) ===
    # =========================================

    def on_mouse_down(self, event):
        x, y = event.x, event.y
        clicked = None
        for n in self.G.nodes:
            dx, dy = self.get_draw_pos(n)
            if math.hypot(x-dx, y-dy) <= self.node_radius:
                clicked = n; break
                
        if clicked is not None:
            self.pre_drag_graph_state = self.G.copy()
            self.drag_node = clicked
            self.drag_start_pos = (x, y); self.is_dragging = False
            # REMOVED: self.handle_click(clicked) <-- This was causing the double-fire issue
        else:
            self.inspected_node = None
            if self.mode in ["ADD_FUNC", "ADD_RES"]: self.save_state(); self.add_node(x, y)
            else: self.redraw()

    def on_mouse_drag(self, event):
        if self.drag_node is not None:
            if math.hypot(event.x-self.drag_start_pos[0], event.y-self.drag_start_pos[1]) > 5: 
                self.is_dragging=True
                if self.view_mode == "FREE":
                    self.G.nodes[self.drag_node]['pos'] = (event.x, event.y)
                else:
                    layer_y = self.jsat_layers[self.get_node_layer(self.G.nodes[self.drag_node])]
                    self.G.nodes[self.drag_node]['pos'] = (event.x, layer_y)
                self.redraw()

    def on_mouse_up(self, event):
        if self.drag_node is not None:
            if self.is_dragging: 
                self.undo_stack.append(self.pre_drag_graph_state)
                if len(self.undo_stack)>self.history_limit: self.undo_stack.pop(0)
                self.redo_stack.clear()
                
                if self.view_mode == "JSAT":
                    new_layer = self.get_layer_from_y(event.y)
                    if new_layer:
                        self.G.nodes[self.drag_node]['layer'] = new_layer
                        self.G.nodes[self.drag_node]['pos'] = (event.x, self.jsat_layers[new_layer])
                        self.redraw()
                        
            else: self.handle_click(self.drag_node)
            self.drag_node=None; self.is_dragging=False

    # --- Standard Handlers ---
    def handle_click(self, node_id):
        self.inspected_node = node_id
        if self.mode == "SELECT": self.redraw()
        elif self.mode == "DELETE": self.save_state(); self.G.remove_node(node_id); self.inspected_node=None; self.redraw()
        elif self.mode == "ADD_EDGE":
            if not self.selected_node: self.selected_node=node_id; self.redraw()
            else:
                if self.selected_node!=node_id:
                    if self.G.nodes[self.selected_node]['type'] != self.G.nodes[node_id]['type']:
                        self.save_state(); self.G.add_edge(self.selected_node, node_id)
                    else: messagebox.showerror("Error", "Bipartite Rule")
                self.selected_node=None; self.redraw()
        elif self.mode == "ASSIGN_AGENT":
            if self.G.nodes[node_id]['agent'] != self.current_agent:
                self.save_state(); self.assign_agent_logic(node_id, self.current_agent); self.redraw()

    def assign_agent_logic(self, node_id, agent_name):
        self.G.nodes[node_id]['agent'] = agent_name
        if self.G.nodes[node_id]['type'] == "Function":
            for n in self.G.successors(node_id): 
                self.G.nodes[n]['agent'] = agent_name

    # --- Utils ---
    def on_double_click(self, event):
        clicked = self.find_node_at(event.x, event.y)
        if clicked is not None:
            self.open_node_editor(clicked)
            
    def open_node_editor(self, nid):
        win = Toplevel(self.root); win.title("Edit Node")
        d = self.G.nodes[nid]
        tk.Label(win, text="Label:").pack()
        e_lbl = tk.Entry(win); e_lbl.insert(0, d.get('label', '')); e_lbl.pack()
        def save():
            self.save_state(); self.G.nodes[nid]['label'] = e_lbl.get(); win.destroy(); self.redraw()
        tk.Button(win, text="Save", command=save).pack(pady=10)

    def create_agent(self):
        n = simpledialog.askstring("Input", "Name:")
        if n and n not in self.agents:
            c = simpledialog.askstring("Input", "Color:")
            if c: self.agents[n]=c; self.refresh_agent_dropdown(); self.agent_var.set(n); self.select_agent(n)
            
    def refresh_agent_dropdown(self):
        if not hasattr(self, 'agent_frame') or not self.agent_frame: return
        if hasattr(self, 'agent_menu'): self.agent_menu.destroy()
        self.agent_menu = tk.OptionMenu(self.agent_frame, self.agent_var, *self.agents.keys(), command=self.select_agent)
        self.agent_menu.pack(side=tk.LEFT)
        
    def select_agent(self, v): self.current_agent=v; self.set_mode("ASSIGN_AGENT")
    def add_node(self, x, y):
        nid = (max(self.G.nodes)+1) if self.G.nodes else 0
        typ = "Function" if self.mode == "ADD_FUNC" else "Resource"
        self.G.add_node(nid, pos=(x, y), type=typ, agent="Unassigned", label="F" if typ=="Function" else "R"); self.redraw()
    def save_state(self):
        self.undo_stack.append(self.G.copy())
        if len(self.undo_stack)>self.history_limit: self.undo_stack.pop(0)
        self.redo_stack.clear()
    def undo(self):
        if self.undo_stack: self.redo_stack.append(self.G.copy()); self.G=self.undo_stack.pop(); self.redraw()
    def redo(self):
        if self.redo_stack: self.undo_stack.append(self.G.copy()); self.G=self.redo_stack.pop(); self.redraw()
    def set_mode(self, m): 
        self.mode=m; self.selected_node=None
        self.status_label.config(text=f"Mode: {'Select' if m=='SELECT' else m}")
        self.redraw()
    def find_node_at(self, x, y):
        for n, d in self.G.nodes(data=True):
            nx, ny = d.get('pos', (0,0))
            if math.hypot(x-nx, y-ny) <= self.node_radius: return n
        return None
    
    # --- Edit/File/Compare Wrappers ---
    def edit_agent(self, old):
        win=Toplevel(self.root); tk.Label(win, text="Name:").pack(); ne=tk.Entry(win); ne.insert(0,old); ne.pack()
        tk.Label(win, text="Color:").pack(); ce=tk.Entry(win); ce.insert(0,self.agents[old]); ce.pack()
        def s():
            nn, nc = ne.get(), ce.get()
            if nn and nc:
                self.save_state(); del self.agents[old]; self.agents[nn]=nc
                for n,d in self.G.nodes(data=True): 
                    if d.get('agent')==old: self.G.nodes[n]['agent']=nn
                self.refresh_agent_dropdown(); self.redraw(); win.destroy()
        tk.Button(win, text="Save", command=s).pack()
    def initiate_save_json(self): self.finalize_json_save(self.G, "curr")
    def finalize_json_save(self, g, n):
        fp=filedialog.asksaveasfilename(initialfile=n, defaultextension=".json")
        if fp: 
            with open(fp,'w') as f: json.dump({"graph_data":nx.node_link_data(g),"agents":self.agents}, f, indent=4)
    def load_from_json(self):
        fp=filedialog.askopenfilename()
        if fp:
            with open(fp,'r') as f: b=json.load(f)
            self.save_state(); self.agents=b.get("agents",{}); self.refresh_agent_dropdown()
            self.G=nx.node_link_graph(b["graph_data"], directed=True)
            for n in self.G.nodes: self.G.nodes[n]['pos']=tuple(self.G.nodes[n]['pos'])
            mapping = {n: int(n) for n in self.G.nodes() if str(n).isdigit()}
            self.G = nx.relabel_nodes(self.G, mapping)
            self.redraw()
    def save_architecture_internal(self):
        n=simpledialog.askstring("Name","Name:"); 
        if n: self.saved_archs[n]=self.G.copy()
    
    # --- COMPARISON ---
    def open_comparison_dialog(self):
        av=["Current"]+list(self.saved_archs.keys())
        if len(av)<1: messagebox.showinfo("Info","No archs"); return
        w=Toplevel(self.root); tk.Label(w,text="Select (Ctrl+Click)").pack()
        lb=tk.Listbox(w,selectmode=tk.MULTIPLE); lb.pack(); [lb.insert(tk.END,o) for o in av]; lb.selection_set(0)
        def go():
            idx=lb.curselection(); names=[lb.get(i) for i in idx]
            gs=[(n, self.G.copy() if n=="Current" else self.saved_archs[n].copy()) for n in names]
            for _,g in gs: self._inject_colors(g)
            w.destroy(); self.launch_compare(gs)
        tk.Button(w,text="Go",command=go).pack()
    def _inject_colors(self, g):
        for n,d in g.nodes(data=True): d['_color_cache']=self.agents.get(d.get('agent'),"white")
        
    def calculate_metric(self, G, metric_name):
        try:
            n = G.number_of_nodes()
            if metric_name == "Nodes": return n
            if metric_name == "Edges": return G.number_of_edges()
            if n == 0: return "0"
            if metric_name == "Density": return f"{nx.density(G):.3f}"
            if metric_name == "Avg Degree": return f"{sum([d for _, d in G.degree()])/n:.2f}"
            if metric_name == "Avg Clustering": return f"{nx.average_clustering(G.to_undirected()):.3f}"
        except: return "Err"
        return ""

    def launch_compare(self, gs):
        w = Toplevel(self.root)
        w.title("Comparative Analytics")
        w.geometry("1200x800")
        
        # Force update so frame sizes are calculated immediately (Fixes centering issue)
        w.update_idletasks()
        
        tf = tk.Frame(w, bd=2, relief=tk.RAISED)
        tf.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        paned = tk.PanedWindow(w, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        graph_container = tk.Frame(paned)
        paned.add(graph_container, minsize=400)
        
        inspector_frame = tk.Frame(paned, bd=2, relief=tk.SUNKEN, bg="#f0f0f0")
        paned.add(inspector_frame, minsize=150)

        def refresh_metrics():
            for widget in tf.winfo_children(): widget.destroy()
            tk.Label(tf, text="System Metrics Comparison", font=("Arial", 12, "bold")).pack(pady=5)
            grid_f = tk.Frame(tf); grid_f.pack(fill=tk.X)
            metrics = ["Nodes", "Edges", "Density", "Avg Degree", "Avg Clustering"]
            
            tk.Label(grid_f, text="Metric", font=("Arial", 10, "bold"), width=15, relief="solid", bd=1).grid(row=0, column=0, sticky="nsew")
            for i, (name, _) in enumerate(gs):
                tk.Label(grid_f, text=name, font=("Arial", 10, "bold"), width=15, relief="solid", bd=1).grid(row=0, column=i+1, sticky="nsew")
            
            for r, m in enumerate(metrics):
                tk.Label(grid_f, text=m, font=("Arial", 10), relief="solid", bd=1).grid(row=r+1, column=0, sticky="nsew")
                for c, (_, g) in enumerate(gs):
                    val = self.calculate_metric(g, m)
                    tk.Label(grid_f, text=str(val), relief="solid", bd=1).grid(row=r+1, column=c+1, sticky="nsew")

        def refresh_inspector(label):
            for widget in inspector_frame.winfo_children(): widget.destroy()
            if not label:
                tk.Label(inspector_frame, text="Click a node to inspect across networks.", bg="#f0f0f0", font=("Arial", 12)).pack(pady=20)
                return
            
            tk.Label(inspector_frame, text=f"Inspecting Node: '{label}'", bg="#f0f0f0", font=("Arial", 12, "bold")).pack(pady=5)
            grid_f = tk.Frame(inspector_frame, bg="#f0f0f0"); grid_f.pack(padx=10, pady=5)
            headers = ["Network", "Agent", "In-Degree", "Out-Degree", "Degree Cent.", "Eigenvector Cent."]
            for i, h in enumerate(headers):
                tk.Label(grid_f, text=h, font=("Arial", 10, "bold"), bg="#ddd", relief="solid", bd=1, width=18).grid(row=0, column=i, sticky="nsew")
            
            for r, (name, g) in enumerate(gs):
                target_node = None
                for n, d in g.nodes(data=True):
                    if d.get('label') == label:
                        target_node = n; break
                
                vals = [name]
                if target_node is not None:
                    d = g.nodes[target_node]
                    vals.append(d.get('agent', 'N/A'))
                    vals.append(g.in_degree(target_node))
                    vals.append(g.out_degree(target_node))
                    try: dc = f"{nx.degree_centrality(g)[target_node]:.3f}"
                    except: dc = "0.00"
                    vals.append(dc)
                    try: ec = f"{nx.eigenvector_centrality(g, max_iter=500).get(target_node, 0):.3f}"
                    except: ec = "0.00"
                    vals.append(ec)
                else:
                    vals.extend(["(Not Found)", "-", "-", "-", "-"])
                
                for c, v in enumerate(vals):
                    tk.Label(grid_f, text=str(v), relief="solid", bd=1, bg="white").grid(row=r+1, column=c, sticky="nsew")

        refresh_metrics()
        refresh_inspector(None)
        
        for n, g in gs:
            InteractiveComparisonPanel(graph_container, g, n, self.node_radius, self.agents, None, refresh_inspector)

if __name__ == "__main__":
    root = tk.Tk()
    app = GraphBuilderApp(root)
    root.mainloop()