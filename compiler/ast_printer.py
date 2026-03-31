import os
import sys
from typing import TextIO

from . import visitor
from .ast import *


class AstPrinter:
    """ Класс для наглядного представления (печати) AST-дерева """

    @visitor.on('AstNode')
    def view_node(self, AstNode):  # noqa
        """ Нужен для работы модуля visitor (инициализации диспетчера) """
        pass

    @visitor.when(AstNode)
    def view_node(self, node: AstNode) -> tuple[str, Sequence[AstNode] | None]:
        """ Реализация по умолчанию """
        return str(node), node.children

    @visitor.when(LiteralNode)
    def view_node(self, node: LiteralNode) -> tuple[str, Sequence[AstNode]]:
        return node.literal, ()

    @visitor.when(AssignNode)
    def view_node(self, node: AssignNode) -> tuple[str, Sequence[ExprNode]]:
        return '=', (node.var, node.value)

    @visitor.when(VarsDeclNode)
    def view_node(self, node: VarsDeclNode) -> tuple[str, Sequence[ExprNode]]:
        return str(node.type), node.vars

    @visitor.when(CallNode)
    def view_node(self, node: CallNode) -> tuple[str, Sequence[ExprNode]]:
        return f'{node.name}()', node.params

    @visitor.when(StmtListNode)
    def view_node(self, node: StmtListNode) -> str | tuple[str, Sequence[StmtNode]]:
        return '...', node.stmts

    @visitor.when(FuncNode)
    def view_node(self, node: FuncNode) -> str | tuple[str, Sequence[AstNode]]:
        params = ', '.join(f'{p.type} {p.vars[0]}' for p in node.params)
        return f'{node.type} {node.name}({params})', (node.body,)

    @visitor.when(TypeConvertNode)
    def view_node(self, node: TypeConvertNode) -> str | tuple[str, Sequence[ExprNode]]:
        return f'({node.type})', (node.value,)

    def tree(self, node: AstNode) -> list[str]:
        name, children = self.view_node(node), ()
        for _ in range(2):
            if isinstance(name, Sequence) and not isinstance(name, str):
                name, *children = name
        if len(children) == 0:
            children = node.children
        elif len(children) == 1:
            children = children[0]

        semantic_info = ''
        if node.node_ident:
            semantic_info = str(node.node_ident)
        elif node.node_type:
            semantic_info = str(node.node_type)
        if isinstance(node, CallNode) and node.name.node_ident:
            semantic_info += f' // {node.name.node_ident}'
        if name and semantic_info:
            name += f' : {semantic_info}'

        result = [name]
        for i, child in enumerate(children):
            ch0, ch = '├', '│'
            if i == len(children) - 1:
                ch0, ch = '└', ' '
            result.extend(((ch0 if j == 0 else ch) + ' ' + s for j, s in enumerate(self.tree(child))))
        return result

    @staticmethod
    def print(node: AstNode, file: TextIO | None = None) -> None:
        printer = AstPrinter()
        print(*printer.tree(node), sep=os.linesep, file=(file or sys.stdout))
