from __future__ import annotations

from pathlib import Path
from typing import Any

from lark import Lark, Transformer, UnexpectedInput

from .ast import *
from .errors import ParserException

grammar_path = Path(__file__).parent / "parser.lark"
grammar = grammar_path.read_text(encoding="utf-8")
parser = Lark(grammar, start="start", parser="earley", propagate_positions=True)


class ASTBuilder(Transformer):
    def _process_meta(self, node: Any, meta) -> Any:
        if isinstance(node, AstNode):
            node.row = getattr(meta, "line", None)
            node.col = getattr(meta, "column", None)
        return node

    def _call_userfunc(self, tree, new_children=None):
        children = new_children if new_children is not None else tree.children
        try:
            func = getattr(self, tree.data)
        except AttributeError:
            result = self.__default__(tree.data, children, tree.meta)
        else:
            result = func(*children)
        return self._process_meta(result, tree.meta)

    def __default_token__(self, token):
        return token

    def stmt_return(self, value=None) -> StmtReturnNode:
        return StmtReturnNode(value)

    def param_list(self, *params) -> ParamListNode:
        return ParamListNode(*params)

    def call_arg_list(self, *args) -> CallArgListNode:
        return CallArgListNode(*args)

    def stmt_list(self, *stmts) -> StmtListNode:
        return StmtListNode(*stmts)

    def body(self, stmt_list: StmtListNode) -> StmtListNode:
        return stmt_list

    def array_suffix(self):
        return "[]"

    def type(self, base_type: TypeNode, *suffixes) -> TypeNode:
        result: TypeNode = base_type
        for _ in suffixes:
            result = TypeArrNode(result)
        return result

    def type_custom(self, ident: IdentNode) -> TypeCustomNode:
        return TypeCustomNode(ident)

    def __getattr__(self, item):
        if isinstance(item, str) and item.upper() == item:
            return lambda x: x

        if item in (
            "mul",
            "div",
            "add",
            "sub",
            "idv",
            "mod",
            "comp_lt",
            "comp_gt",
            "comp_le",
            "comp_ge",
            "comp_eq",
            "comp_nq",
            "logic_and",
            "logic_or",
        ):
            return lambda *args: BinOpNode(BinOp[item.upper()], *args)

        if item in (
            "unary_inc",
            "unary_dec",
            "prefix_inc",
            "prefix_dec",
            "postfix_inc",
            "postfix_dec",
            "logic_not",
        ):
            return lambda *args: UnoOpNode(UnoOp[item.upper()], *args)

        if item in (
            "assign",
            "assign_add",
            "assign_sub",
            "assign_mul",
            "assign_div",
            "assign_idv",
            "assign_mod",
        ):
            return lambda *args: AssignNode(Assign[item.upper()], *args)

        return lambda *args: eval("".join(x.capitalize() or "_" for x in item.split("_")) + "Node")(*args)


def parse(program: str) -> StmtListNode:
    try:
        parse_tree = parser.parse(str(program))
    except UnexpectedInput as e:
        context = e.get_context(str(program), span=40) if hasattr(e, "get_context") else ""
        message = "Синтаксическая ошибка"
        if context:
            message += f":\n{context}"
        raise ParserException(message, row=getattr(e, "line", None), col=getattr(e, "column", None))

    ast_tree: StmtListNode = ASTBuilder().transform(parse_tree)
    ast_tree.program = True
    return ast_tree
