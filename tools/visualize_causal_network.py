#!/usr/bin/env python3
"""Render a static PNG and interactive HTML view of the high-confidence
causal network (SNP -> Gene -> Trait, plus Trait -> Trait if present).

Generalizes the old 21_visualize_causal_network.py: paths and the
PIP/SMR-p significance thresholds are CLI args instead of being hardcoded.
"""
import argparse

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pyvis.network import Network
from adjustText import adjust_text


def visualize_causal_network(nodes_path, edges_path, output_png, output_html, pip_threshold, smr_p_threshold):
    nodes_df = pd.read_csv(nodes_path)
    edges_df = pd.read_csv(edges_path)

    print(f"Filtering for high-confidence links (PIP >= {pip_threshold}, SMR_p < {smr_p_threshold})...")

    prog_edges = edges_df[edges_df["type"] == "Disease Progression"]

    snp_gene_filtered = edges_df[
        (edges_df["type"] == "SNP-Gene (Validated)")
        & (edges_df["weight"] >= pip_threshold)
        & (edges_df["smr_p"] < smr_p_threshold)
        & (edges_df["target"] != "NO_GENE_MAPPED")
    ]

    significant_genes = set(snp_gene_filtered["target"].unique())

    gene_trait_filtered = edges_df[
        (edges_df["type"] == "Gene-Trait (Discovery)") & (edges_df["source"].isin(significant_genes))
    ]

    edges_df_filtered = pd.concat([prog_edges, snp_gene_filtered, gene_trait_filtered])

    active_nodes = set(edges_df_filtered["source"]).union(set(edges_df_filtered["target"]))
    nodes_df_filtered = nodes_df[nodes_df["id"].isin(active_nodes)]

    G = nx.DiGraph()
    for _, row in nodes_df_filtered.iterrows():
        G.add_node(row["id"], label=row["label"], group=row["group"], color=row["color"])
    for _, row in edges_df_filtered.iterrows():
        if row["source"] in G and row["target"] in G:
            G.add_edge(row["source"], row["target"], type=row["type"], weight=row["weight"], prob=row.get("prob", 1.0))

    # --- Static PNG ---
    plt.figure(figsize=(20, 16))

    traits = [n for n, d in G.nodes(data=True) if d.get("group") == "Trait"]
    genes = [n for n, d in G.nodes(data=True) if d.get("group") == "Gene" and n != "NO_GENE_MAPPED"]
    snps = [n for n, d in G.nodes(data=True) if d.get("group") == "SNP"]

    pos_seed = {}
    pos_seed.update({node: (0, i) for i, node in enumerate(snps)})
    pos_seed.update({node: (1, i * (max(1, len(snps)) / max(1, len(genes)))) for i, node in enumerate(genes)})
    pos_seed.update({node: (2, i * (max(1, len(snps)) / max(1, len(traits)))) for i, node in enumerate(traits)})

    pos = nx.spring_layout(G, pos=pos_seed, fixed=traits if traits else None, k=0.3, iterations=50)

    node_colors = [d.get("color", "gray") for n, d in G.nodes(data=True)]
    node_sizes = [4000 if d.get("group") == "Trait" else 1200 if d.get("group") == "Gene" else 300 for n, d in G.nodes(data=True)]
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.7)

    progression_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("type") == "Disease Progression"]
    snp_gene_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("type") == "SNP-Gene (Validated)"]
    gene_trait_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("type") == "Gene-Trait (Discovery)"]

    nx.draw_networkx_edges(G, pos, edgelist=progression_edges, width=4, edge_color="red", arrowsize=25)
    nx.draw_networkx_edges(G, pos, edgelist=snp_gene_edges, width=0.8, edge_color="gray", style="dashed", alpha=0.4)
    nx.draw_networkx_edges(G, pos, edgelist=gene_trait_edges, width=1.5, edge_color="blue", alpha=0.5)

    texts = []
    for n, d in G.nodes(data=True):
        if d.get("group") in ["Trait", "Gene"]:
            x, y = pos[n]
            texts.append(plt.text(x, y, d.get("label", n), fontsize=9, fontweight="bold"))

    if texts:
        print("Adjusting text labels (this may take a minute)...")
        adjust_text(texts, arrowprops=dict(arrowstyle="->", color="black", lw=0.5))

    legend_elements = [
        Line2D([0], [0], color="red", lw=3, label="Disease Progression"),
        Line2D([0], [0], color="blue", lw=1.5, label="Gene-Trait (Discovery)"),
        Line2D([0], [0], color="gray", lw=1, ls="--", label="SNP-Gene (Validated)"),
        Line2D([0], [0], marker="o", color="w", label="Trait", markerfacecolor="red", markersize=15),
        Line2D([0], [0], marker="o", color="w", label="Gene", markerfacecolor="blue", markersize=10),
        Line2D([0], [0], marker="o", color="w", label="SNP", markerfacecolor="gray", markersize=6),
    ]
    plt.legend(handles=legend_elements, loc="upper left", fontsize=12)
    plt.title("High-Confidence Causal Network (COJO + SuSiE + SMR Significant)", fontsize=22)
    plt.axis("off")
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    print(f"Static visualization saved to: {output_png}")

    # --- Interactive HTML ---
    print("Generating high-confidence interactive HTML visualization...")
    net = Network(height="1000px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
    net.force_atlas_2based()

    for n, d in G.nodes(data=True):
        group = d.get("group", "SNP")
        color = d.get("color", "gray")
        label = d.get("label", n)
        size = 40 if group == "Trait" else 25 if group == "Gene" else 15
        net.add_node(n, label=label, title=f"ID: {n}\nGroup: {group}", color=color, size=size)

    for u, v, d in G.edges(data=True):
        etype = d.get("type", "Unknown")
        color = "red" if etype == "Disease Progression" else "blue" if "Gene-Trait" in etype else "gray"
        width = 5 if etype == "Disease Progression" else 2
        dashed = etype == "SNP-Gene (Validated)"
        net.add_edge(u, v, title=etype, color=color, width=width, dashes=dashed)

    net.set_options("""
    var options = {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -100,
          "centralGravity": 0.01,
          "springLength": 100,
          "springConstant": 0.08,
          "avoidOverlap": 1
        },
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based"
      }
    }
    """)

    net.save_graph(output_html)
    print(f"Interactive visualization saved to: {output_html}")


def main():
    parser = argparse.ArgumentParser(description="Visualize the causal network produced by extract_graph_table.py")
    parser.add_argument("--nodes", required=True)
    parser.add_argument("--edges", required=True)
    parser.add_argument("--output_png", required=True)
    parser.add_argument("--output_html", required=True)
    parser.add_argument("--pip_threshold", type=float, default=0.5)
    parser.add_argument("--smr_p_threshold", type=float, default=0.05)
    args = parser.parse_args()

    visualize_causal_network(args.nodes, args.edges, args.output_png, args.output_html, args.pip_threshold, args.smr_p_threshold)


if __name__ == "__main__":
    main()
