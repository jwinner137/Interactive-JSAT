# utils.py
# Handles the "Heavy Lifting" math. This is where your metric calculations live. 
# If you want to add a new metric (e.g., "PageRank"), you add it here.

import networkx as nx

def calculate_metric(G, metric_name):
    """
    Calculates a specific network metric for a given graph G.
    Returns a string representation of the result or 'Err'.
    """
    try:
        n = G.number_of_nodes()
        
        if metric_name == "Nodes": 
            return n
        
        if metric_name == "Edges": 
            return G.number_of_edges()
        
        if n == 0: 
            return "0"
        
        if metric_name == "Density": 
            return f"{nx.density(G):.3f}"
        
        if metric_name == "Avg Degree": 
            avg_deg = sum([d for _, d in G.degree()]) / n
            return f"{avg_deg:.2f}"
        
        if metric_name == "Avg Clustering": 
            # Note: Average clustering is typically for undirected graphs, 
            # so we convert to undirected for this specific metric.
            avg_clust = nx.average_clustering(G.to_undirected())
            return f"{avg_clust:.3f}"
            
    except Exception as e:
        print(f"Error calculating {metric_name}: {e}")
        return "Err"
    
    return ""