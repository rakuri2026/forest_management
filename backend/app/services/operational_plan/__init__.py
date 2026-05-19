"""
Operational Plan Document Builder Service
"""
from .tree_models import TreeNode, TreeOperations, DocumentTree
from .auto_numbering import recompute_numbers, to_devanagari_number, DEVANAGARI_DIGITS
from .seed_data import get_default_seed_tree, get_appendix_seed_nodes
from .variable_registry import VARIABLE_REGISTRY, VariableDef, get_variable, get_variables_by_category
from .variable_resolver import VariableResolver

__all__ = [
    "TreeNode", "TreeOperations", "DocumentTree",
    "recompute_numbers", "to_devanagari_number", "DEVANAGARI_DIGITS",
    "get_default_seed_tree", "get_appendix_seed_nodes",
    "VARIABLE_REGISTRY", "VariableDef", "get_variable", "get_variables_by_category",
    "VariableResolver",
]
