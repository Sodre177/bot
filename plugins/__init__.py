"""
This module makes all modules in a specified namespace (plugins_namespace)
behave slightly differently.

We track whenever one plugin imports another, and keep a dependency graph
around. We provide high level unload/reload functions that will unload/reload
dependent plugins as well. We also provide a way for a plugin to hook a
"finalizer" to be executed when the plugin is to be unloaded.
"""

import importlib.machinery
import importlib.util
import builtins
import types
import sys
import atexit
import util.digraph

plugins_namespace = "plugins"
def is_plugin(name):
    return name.startswith(plugins_namespace + ".")

deps = util.digraph.Digraph()
import_stack = []

def current_plugin():
    """
    In the lexical scope of the plugin, __name__ will refer to the plugin's
    name.  This function can be used to get the name of the plugin in the
    *dynamic* scope of its initialization. In other words functions outside a
    plugin can get to know its name if they were called during plugin
    initialization.
    """
    if not len(import_stack):
        raise ValueError("not called during plugin initialization")
    return import_stack[-1]

def trace_import(name, globals=None, locals=None, fromlist=(), level=0):
    name_parts = name.split(".")
    for i in range(1, len(name_parts) + 1):
        parent = ".".join(name_parts[:i])
        if is_plugin(parent):
            deps.add_edge(current_plugin(), parent)
    return builtins.__import__(name, globals, locals, fromlist, level)

trace_builtins = types.ModuleType(builtins.__name__)
trace_builtins.__dict__.update(builtins.__dict__)
trace_builtins.__import__ = trace_import

finalizers = {}


def finalizer(fin):
    """
    A decorator for registering a finalizer, which will be called during
    unloading/reloading of a plugin. E.g.:

        log = open("log", "w")
        @plugins.finalizer
        def close_log():
            log.close()

    If a module initialization fails to complete, the finalizers that managed
    to register will be called.
    """

    current = current_plugin()
    if current not in finalizers:
        finalizers[current] = []
    finalizers[current].append(fin)
    return fin

def finalize_module(name):
    if name not in finalizers:
        return
    gen = finalizers[name].__iter__()
    def cont_finalizers():
        try:
            for fin in gen:
                fin()
        except:
            cont_finalizers()
            raise
        del finalizers[name]
    cont_finalizers()

class PluginLoader(importlib.machinery.SourceFileLoader):
    __slots__ = ()
    def exec_module(self, mod):
        name = mod.__name__
        mod.__builtins__ = trace_builtins
        import_stack.append(name)
        try:
            super().exec_module(mod)
        except:
            try:
                finalize_module(name)
            finally:
                deps.del_edges_from(name)
            raise
        finally:
            import_stack.pop()

class PluginFinder(importlib.machinery.PathFinder):
    __slots__ = ()
    @classmethod
    def find_spec(self, name, path=None, target=None):
        name_parts = name.split(".")
        if not is_plugin(name):
            return
        spec = super().find_spec(name, path, target)
        if spec == None:
            return
        spec.loader = PluginLoader(spec.loader.name, spec.loader.path)
        return spec

for i in range(len(sys.meta_path)):
    if sys.meta_path[i] == importlib.machinery.PathFinder:
        sys.meta_path.insert(i, PluginFinder)

def unsafe_unload(name):
    """
    Finalize and unload a single plugin. May break any plugins that depend on
    it. All finalizers will be executed even if some raise exceptions, if there
    were any they will all be reraised together.
    """
    if not is_plugin(name):
        raise ValueError(name + " is not a plugin")
    try:
        finalize_module(name)
    finally:
        deps.del_edges_from(name)
        del sys.modules[name]

def unload(name):
    """
    Finalize and unload a plugin and any plugins that (transitively) depend on
    it. All finalizers will be executed even if some raise exceptions, if there
    were any they will all be reraised together.
    """
    gen = deps.subgraph_paths_to(name).topo_sort_fwd()
    def cont_unload():
        try:
            for dep in gen:
                if dep != name:
                    unsafe_unload(dep)
        except:
            cont_unload()
            raise
        unsafe_unload(name)
    cont_unload()

def unsafe_reload(name):
    """
    Finalize and reload a single plugin. This will run the new plugin code over
    the same module object, which may break any plugins that depend on it. All
    finalizers will be executed even if some raise exceptions. If there were any
    or if there was an exception during reinitialization, they will all be
    reraised together. If plugin initialization raises an exception the plugin
    remains loaded but may be in a half-updated state. Its finalizers aren't run
    immediately. Returns the module object if successful.
    """
    if not is_plugin(name):
        raise ValueError(name + " is not a plugin")
    try:
        finalize_module(name)
    finally:
        deps.del_edges_from(name)
        ret = importlib.reload(sys.modules[name])
    return ret

def reload(name):
    """
    Finalize and reload a plugin and any plugins that (transitively) depend on
    it. We try to run all finalizers in dependency order, and only load plugins
    that were successfully unloaded, and whose dependencies have been
    successfully reloaded. If a plugin fails to initialize, we run any
    finalizers it managed to register, and the plugin is not loaded. Any
    exceptions raised will be reraised together. Returns the module object of
    the requested plugin if successful.
    """
    reloads = deps.subgraph_paths_to(name)
    unload_success = set()
    reload_success = set()
    unload_gen = reloads.topo_sort_fwd()
    reload_gen = reloads.topo_sort_bck()
    def cont_reload():
        try:
            for dep in reload_gen:
                if (dep in unload_success and
                    all(m in reload_success for m in reloads.edges_from(dep))):
                    importlib.import_module(dep)
                    reload_success.add(dep)
        except:
            cont_reload()
            raise
    def cont_unload():
        try:
            for dep in unload_gen:
                if dep != name:
                    unsafe_unload(dep)
                    unload_success.add(dep)
        except:
            cont_unload()
            raise
        try:
            unsafe_unload(name)
        except:
            cont_reload()
            raise
        try:
            ret = importlib.import_module(name)
            reload_success.add(name)
        finally:
            cont_reload()
        return ret
    return cont_unload()

def load(name):
    """
    Load a single plugin. If it's already loaded, nothing is changed. If there
    was an exception during initialization, the finalizers that managed to
    registers will be run. Returns the module object if successful.
    """
    if not is_plugin(name):
        raise ValueError(name + " is not a plugin")
    if name in sys.modules:
        return sys.modules[name]
    return importlib.import_module(name)

@atexit.register
def atexit_unload():
    unload_gen = list(deps.topo_sort_fwd()).__iter__()
    def cont_unload():
        try:
            for dep in unload_gen:
                unsafe_unload(dep)
        except:
            cont_unload()
            raise
    cont_unload()
