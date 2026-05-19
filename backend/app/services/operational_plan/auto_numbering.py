from typing import List
from .tree_models import TreeNode

DEVANAGARI_DIGITS = {
    0: "०", 1: "१", 2: "२", 3: "३", 4: "४",
    5: "५", 6: "६", 7: "७", 8: "८", 9: "९",
}


def to_devanagari_number(n: int) -> str:
    if n == 0:
        return "०"
    result = ""
    while n > 0:
        result = DEVANAGARI_DIGITS[n % 10] + result
        n //= 10
    return result


def _num(n: int, language: str) -> str:
    return to_devanagari_number(n) if language == "NP" else str(n)


def recompute_numbers(tree: List[TreeNode], language: str = "NP") -> None:
    section_counter = 0
    appendix_counter = 0

    for node in list(tree):
        if node.type in ("preamble", "toc"):
            node.number = None
            node.level = 0
            recompute_numbers(node.children, language)

        elif node.type == "section":
            section_counter += 1
            node.number = _num(section_counter, language)
            node.level = 0
            _number_descendants(node, language, 1)

        elif node.type == "appendix":
            appendix_counter += 1
            node.number = _num(appendix_counter, language)
            node.level = 0
            _number_descendants(node, language, 1)

        else:
            recompute_numbers(node.children, language)


def _number_descendants(parent: TreeNode, language: str, depth: int) -> None:
    for i, child in enumerate(parent.children):
        child_num = i + 1
        num_str = _num(child_num, language)
        child.number = f"{parent.number}.{num_str}"
        child.level = depth
        _number_descendants(child, language, depth + 1)
