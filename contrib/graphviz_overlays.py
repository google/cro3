#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to visualize the inheritance of portage overlays using graphviz.

Usage example (write graph to output_file.dot, and trim the visualization to
just show what samus-private:base and auron_yuna:base requires):
  graphviz_overlays.py -o output_file.dot -r samus-private:base auron_yuna:base

This is contrib-quality code.  Don't make something that really depends on it ;)
"""

import argparse
import collections
import os
import pathlib
import sys


def dot_repr_str(str_to_repr):
    """Represent a string compatible with dot syntax.

    Args:
        str_to_repr: The string to represent.

    Returns:
        The string, in dot lanugage compatible syntax.
    """
    out = repr(str_to_repr)
    if out.startswith("'"):
        out = '"{}"'.format(out[1:-1].replace("'", "\\'"))
    return out


class Digraph:
    """Class representing a directed graph structure."""
    def __init__(self, stylesheet=None):
        self.nodes = {}
        self.edges = []
        self.subgraphs = {}
        self.subgraph_items = collections.defaultdict(set)
        self.stylesheet = stylesheet

    def cut_to_roots(self, roots):
        """Reduce a graph to only the specified nodes and their children.

        Args:
            roots: A list of the nodes desired.

        Returns:
            A new Digraph.
        """
        g = Digraph(stylesheet=self.stylesheet)
        id_to_name = {v: k for k, v in self.nodes.items()}

        def add_node(node):
            if node in g.nodes:
                return
            g.add_node(node)
            for from_e, to_e in self.edges:
                if from_e == self.nodes[node]:
                    to_node = id_to_name[to_e]
                    add_node(to_node)
                    g.add_edge(node, to_node)

        for node in roots:
            add_node(node)

        for subgraph_name, subgraph_id in self.subgraphs.items():
            for node in self.subgraph_items[subgraph_id]:
                if id_to_name[node] in g.nodes:
                    g.subgraph_set(subgraph_name, id_to_name[node])

        return g


    def add_node(self, name, subgraph=None):
        """Add a node to the graph, or do nothing if it already exists.

        Args:
            name: The node label.
            subgraph: Optionally, the subgraph to appear in.
        """
        if name in self.nodes:
            # Node already added
            return
        nid = 'N{}'.format(len(self.nodes) + 1)
        self.nodes[name] = nid
        if subgraph:
            self.subgraph_set(subgraph, name)

    def subgraph_set(self, name, node_name):
        """Set the subgraph of a node.

        Args:
            name: The subgraph.
            node_name: The node.
        """
        if name not in self.subgraphs:
            cid = 'cluster_{}'.format(len(self.subgraphs) + 1)
            self.subgraphs[name] = cid
        else:
            cid = self.subgraphs[name]
        self.subgraph_items[cid].add(self.nodes[node_name])

    def add_edge(self, from_node, to_node):
        """Add an edge to the graph.

        Args:
            from_node: The starting node.
            to_node: The ending node.
        """
        self.edges.append((self.nodes[from_node], self.nodes[to_node]))

    def to_dot(self, output_file=sys.stdout):
        """Generate a dot-format representation of the graph.

        Args:
            output_file: The file to write to.
        """
        output_file.write('digraph {\n')
        if self.stylesheet:
            output_file.write(
                'graph [stylesheet={}]\n'.format(dot_repr_str(self.stylesheet)))
        output_file.write('node [shape=box, style=rounded]\n')
        for node_label, node_id in self.nodes.items():
            output_file.write('{} [label={}]\n'.format(
                node_id, dot_repr_str(node_label)))
        for subgraph_label, subgraph_id in self.subgraphs.items():
            output_file.write('subgraph {}'.format(subgraph_id))
            output_file.write(' {\n')
            output_file.write('label = {}\n'.format(
                dot_repr_str(subgraph_label)))
            output_file.write('{}\n'.format(
                '; '.join(self.subgraph_items[subgraph_id])))
            output_file.write('}\n')
        for from_nid, to_nid in self.edges:
            output_file.write('{} -> {}\n'.format(from_nid, to_nid))
        output_file.write('}\n')


def add_profiles(graph, repo_name, path, basedir=None):
    """Add profiles from a portage overlay to the graph.

    Args:
        graph: The graph to add to.
        repo_name: The Portage "repo-name".
        path: The path to the "profiles" directory in the overlay.
        basedir: Used for recursive invocation by this function.

    Yields:
        Each of the profiles added to this graph in this overlay only.
    """

    if not basedir:
        basedir = path
    for ent in path.iterdir():
        if ent.is_dir():
            yield from add_profiles(graph, repo_name, ent, basedir=basedir)
        elif ent.name == 'parent':
            pname = '{}:{}'.format(repo_name, path.relative_to(basedir))
            graph.add_node(pname)
            yield pname
            with open(ent, 'r') as f:
                for line in f:
                    line, _, _ = line.partition('#')
                    line = line.strip()
                    if not line:
                        continue
                    if ':' in line:
                        cname = line
                    else:
                        cname = '{}:{}'.format(
                            repo_name,
                            (path / line).resolve().relative_to(basedir))
                    graph.add_node(cname)
                    graph.add_edge(pname, cname)
                    if cname.startswith('{}:'.format(repo_name)):
                        yield cname
        elif ent.name in ('package.use', 'make.defaults'):
            pname = '{}:{}'.format(repo_name, path.relative_to(basedir))
            graph.add_node(pname)
            yield pname


def add_overlay(path, graph):
    """Add an overlay to the graph.

    Args:
        path: The path to the overlay.
        graph: The graph to add to.
    """
    with open(path / 'metadata' / 'layout.conf') as f:
        for line in f:
            k, part, v = line.partition('=')
            if not part:
                continue
            if k.strip() == 'repo-name':
                repo_name = v.strip()
                break
        else:
            repo_name = path.name
    subgraph = repo_name
    if path.parent.name == 'private-overlays':
        subgraph = 'Private Overlays'
    elif path.parent.name == 'overlays':
        subgraph = 'Public Overlays'
    for profile in add_profiles(graph, repo_name, path / 'profiles'):
        graph.subgraph_set(subgraph, profile)


def find_overlays(path, max_depth=10, skip_dirs=()):
    """Generator to find all portage overlays in a directory.

    Args:
        path: Path to begin search.
        max_depth: Maximum recursion depth.
        skip_dirs: Optional set of paths to skip.
    """
    if path.name == '.git':
        return
    if max_depth == 0:
        return
    for d in path.iterdir():
        if d in skip_dirs:
            continue
        if d.is_dir():
            if (d / 'metadata' / 'layout.conf').is_file():
                yield d
            else:
                yield from find_overlays(d, max_depth=max_depth - 1)


def get_default_src_dir():
    """Find the path to ~/trunk/src."""
    home = pathlib.Path(os.getenv('HOME'))
    for path in (home / 'trunk' / 'src',
                 home / 'chromiumos' / 'src',
                 pathlib.Path('mnt') / 'host' / 'source' / 'src'):
        if path.is_dir():
            return path
    raise OSError(
        'Cannot find path to ~/trunk/src.  '
        'You may need to manually specify --src-dir.')


def main():
    """The main function."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src-dir', type=pathlib.Path)
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w'), default=sys.stdout)
    parser.add_argument('-r', '--roots', nargs='*')
    parser.add_argument(
        '--stylesheet',
        # pylint: disable=line-too-long
        default='https://g3doc.corp.google.com/frameworks/g3doc/includes/graphviz-style.css',
        # pylint: enable=line-too-long
    )
    args = parser.parse_args()

    src_dir = args.src_dir
    if not src_dir:
        src_dir = get_default_src_dir()
    src_dir = src_dir.resolve()

    g = Digraph(stylesheet=args.stylesheet)
    for d in find_overlays(src_dir, skip_dirs=(src_dir / 'platform',
                                               src_dir / 'platform2')):
        if not (d / 'profiles').is_dir():
            print('WARNING: skipping {} due to missing profiles dir'.format(d),
                  file=sys.stderr)
            continue
        add_overlay(d, g)

    if args.roots:
        g = g.cut_to_roots(args.roots)
    g.to_dot(args.output)


if __name__ == '__main__':
    main()
