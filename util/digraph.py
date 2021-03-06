class Digraph:
    """A directed graph with no isolated vertices and no duplicate edges."""

    __slots__ = "fwd", "bck"

    def __init__(self):
        """Create an empty graph."""
        self.fwd = {}
        self.bck = {}

    def add_edge(self, x, y):
        """Add an edge from x to y."""
        if x not in self.fwd:
            self.fwd[x] = set()
        self.fwd[x].add(y)
        if y not in self.bck:
            self.bck[y] = set()
        self.bck[y].add(x)

    def edges_to(self, x):
        """Return a (read-only) set of edges into x."""
        return self.bck[x] if x in self.bck else set()

    def edges_from(self, x):
        """Return a (read-only) set of edges from x."""
        return self.fwd[x] if x in self.fwd else set()

    def subgraph_paths_to(self, x):
        """
        Return an induced subgraph of exactly those vertices that can reach x
        via a path.
        """
        graph = Digraph()
        seen = set()
        def dfs(x):
            if x in seen:
                return
            seen.add(x)
            if x in self.bck:
                for y in self.bck[x]:
                    graph.add_edge(y, x)
                    dfs(y)
        dfs(x)
        return graph

    def topo_sort_fwd(self):
        """
        Iterate through vertices in such a way that whenever there is an edge
        from x to y, x will come up earlier in iteration than y.
        """
        seen = set()
        def dfs(x):
            if x in seen:
                return
            seen.add(x)
            if x in self.bck:
                for y in self.bck[x]:
                    yield from dfs(y)
            yield x
        for x in self.fwd:
            yield from dfs(x)
        for x in self.bck:
            yield from dfs(x)

    def topo_sort_bck(self):
        """
        Iterate through vertices in such a way that whenever there is an edge
        from x to y, x will come up later in iteration than y.
        """
        seen = set()
        def dfs(x):
            if x in seen:
                return
            seen.add(x)
            if x in self.fwd:
                for y in self.fwd[x]:
                    yield from dfs(y)
            yield x
        for x in self.bck:
            yield from dfs(x)
        for x in self.fwd:
            yield from dfs(x)

    def del_edges_from(self, x):
        """
        Delete all edges from x.
        """
        if x in self.fwd:
            for y in self.fwd[x]:
                self.bck[y].discard(x)
            del self.fwd[x]

    def del_edges_to(self, x):
        """
        Delete all edges into x.
        """
        if x in self.bck:
            for y in self.bck[x]:
                self.fwd[y].discard(x)
            del self.bck[x]
