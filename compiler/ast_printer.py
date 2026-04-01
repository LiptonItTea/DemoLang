import os
import sys
from typing import Sequence, TextIO

from . import visitor
from .ast import *


class AstPrinter:
    @visitor.on("AstNode")
    def view_node(self, AstNode):  # noqa
        pass

    @visitor.when(AstNode)
    def view_node(self, node: AstNode) -> tuple[str, Sequence[AstNode] | None]:
        return str(node), node.childs

    @visitor.when(NumNode)
    def view_node(self, node: NumNode) -> tuple[str, Sequence[AstNode]]:
        return node.literal, ()

    @visitor.when(StringNode)
    def view_node(self, node: StringNode) -> tuple[str, Sequence[AstNode]]:
        return node.literal, ()

    @visitor.when(SqStringNode)
    def view_node(self, node: SqStringNode) -> tuple[str, Sequence[AstNode]]:
        return node.literal, ()

    @visitor.when(AssignNode)
    def view_node(self, node: AssignNode) -> tuple[str, Sequence[AstNode]]:
        return node.assignment.value, (node.dest, node.src)

    @visitor.when(CreateVarNode)
    def view_node(self, node: CreateVarNode) -> tuple[str, Sequence[AstNode]]:
        return f"declare {node.type}", node.var_decls

    @visitor.when(CallArgListNode)
    def view_node(self, node: CallArgListNode) -> tuple[str, Sequence[AstNode]]:
        return "args", node.args

    @visitor.when(FuncCallNode)
    def view_node(self, node: FuncCallNode) -> tuple[str, Sequence[AstNode]]:
        if isinstance(node.entity, IdentNode):
            return f"{node.entity}()", node.call_arg.args
        return "call()", (node.entity, *node.call_arg.args)

    @visitor.when(StmtListNode)
    def view_node(self, node: StmtListNode) -> tuple[str, Sequence[AstNode]]:
        return "...", node.stmts

    @visitor.when(FuncDefNode)
    def view_node(self, node: FuncDefNode) -> tuple[str, Sequence[AstNode]]:
        params = []
        for param in node.params.param_decls:
            suffix = "[]" if isinstance(param, ArrayParamDeclNode) else ""
            params.append(f"{param.type} {param.ident}{suffix}")
        return f"{node.return_type} {node.func_name}({', '.join(params)})", (node.body,)

    @visitor.when(StructDefNode)
    def view_node(self, node: StructDefNode) -> tuple[str, Sequence[AstNode]]:
        return f"struct {node.name}", (node.body,)

    @visitor.when(ConditionIfNode)
    def view_node(self, node: ConditionIfNode) -> tuple[str, Sequence[AstNode]]:
        return "if", (node.condition, *node.branches)

    @visitor.when(ConditionWhileNode)
    def view_node(self, node: ConditionWhileNode) -> tuple[str, Sequence[AstNode]]:
        return "while", (node.condition, node.branch)

    @visitor.when(ConditionDoWhileNode)
    def view_node(self, node: ConditionDoWhileNode) -> tuple[str, Sequence[AstNode]]:
        return "do-while", (node.branch, node.condition)

    @visitor.when(ConditionForNode)
    def view_node(self, node: ConditionForNode) -> tuple[str, Sequence[AstNode]]:
        return "for", (node.init, node.condition, node.change, node.body)

    @visitor.when(TypeConvertNode)
    def view_node(self, node: TypeConvertNode) -> tuple[str, Sequence[AstNode]]:
        return f"({node.type})", (node.value,)

    def tree(self, node: AstNode) -> list[str]:
        name, children = self.view_node(node), ()
        for _ in range(2):
            if isinstance(name, Sequence) and not isinstance(name, str):
                name, *children = name

        if len(children) == 0:
            children = node.childs
        elif len(children) == 1:
            children = children[0]

        semantic_info = ""
        if node.node_ident:
            semantic_info = str(node.node_ident)
        elif node.node_type:
            semantic_info = str(node.node_type)

        if isinstance(node, FuncCallNode) and getattr(node.entity, "node_ident", None):
            semantic_info += f" // {node.entity.node_ident}"

        if name and semantic_info:
            name += f" : {semantic_info}"

        result = [name]
        for i, child in enumerate(children):
            ch0, ch = "├", "│"
            if i == len(children) - 1:
                ch0, ch = "└", " "
            result.extend(((ch0 if j == 0 else ch) + " " + s for j, s in enumerate(self.tree(child))))
        return result

    @staticmethod
    def print(node: AstNode, file: TextIO | None = None) -> None:
        printer = AstPrinter()
        print(*printer.tree(node), sep=os.linesep, file=(file or sys.stdout))
