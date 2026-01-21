# config.py
# Stores all your "Magic Numbers" and settings. If you want to change the layer names, heights, or default colors, 
# you do it here without touching the logic code.

# --- Graph Settings ---
NODE_RADIUS = 20
HISTORY_LIMIT = 40

# --- Default Agents ---
DEFAULT_AGENTS = {"Unassigned": "white"}
DEFAULT_CURRENT_AGENT = "Unassigned"

# --- View Modes ---
VIEW_MODE_FREE = "FREE"
VIEW_MODE_JSAT = "JSAT"

# --- JSAT Layer Definitions ---
# Defines the Y-coordinate for each layer
JSAT_LAYERS = {
    "Synchronicity Functions": 100,
    "Coordination Grounding": 250,
    "Distributed Work": 400,
    "Base Environment": 550
}

# Defines the order in which they appear (Top to Bottom)
LAYER_ORDER = [
    "Synchronicity Functions", 
    "Coordination Grounding", 
    "Distributed Work", 
    "Base Environment"
]