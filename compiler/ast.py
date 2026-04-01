from __future__ import annotations

from abc import ABC, abstractmethod
from ast import literal_eval
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional, Tuple

if TYPE_CHECKING:
    from .semantic import IdentDesc, IdentScope, SemanticChecker, TypeDesc  # noqa


class AstNode(ABC):
    def __init__(self) -> None:
        self.row: int | None = None
        self.col: int | None = None
        self.node_type: TypeDesc | None = None
        self.node_ident: IdentDesc | None = None

    @property
    def childs(self) -> Tuple["AstNode", ...]:
        return ()

    @property
    def children(self) -> Tuple["AstNode", ...]:
        return self.childs

    @property
    def tree(self) -> list[str]:
        result = [str(self)]
        for i, child in enumerate(self.childs):
            ch0, ch = "├", "│"
            if i == len(self.childs) - 1:
                ch0, ch = "└", " "
            result.extend(((ch0 if j == 0 else ch) + " " + s for j, s in enumerate(child.tree)))
        return result

    def visit(self, func: Callable[["AstNode"], None]) -> None:
        func(self)
        for child in self.childs:
            child.visit(func)

    def semantic_check(self, checker: "SemanticChecker", scope: "IdentScope") -> None:
        checker.semantic_check(self, scope)

    def __getitem__(self, index: int) -> "AstNode | None":
        return self.childs[index] if index < len(self.childs) else None

    @abstractmethod
    def __str__(self) -> str:
        raise NotImplementedError


class NumNode(AstNode):
    def __init__(self, num: Any):
        super().__init__()
        self.literal = str(num)
        if any(ch in self.literal.lower() for ch in (".", "e")):
            self.value: int | float = float(self.literal)
        else:
            self.value = int(self.literal)

    def __str__(self) -> str:
        return self.literal


class IdentNode(AstNode):
    def __init__(self, name: Any):
        super().__init__()
        self.name = str(name)

    def __str__(self) -> str:
        return self.name


class StringNode(AstNode):
    def __init__(self, value: Any):
        super().__init__()
        self.literal = str(value)
        self.value = literal_eval(self.literal)

    def __str__(self) -> str:
        return self.literal


class SqStringNode(AstNode):
    def __init__(self, value: Any):
        super().__init__()
        self.literal = str(value)
        self.value = literal_eval(self.literal)

    def __str__(self) -> str:
        return self.literal


class TypeNode(AstNode):
    type: "TypeDesc | None" = None

    @property
    def desc(self) -> str:
        return str(self)


class TypeSimpleCharNode(TypeNode):
    @property
    def desc(self) -> str:
        return "char"

    def __str__(self) -> str:
        return "char"


class TypeSimpleIntNode(TypeNode):
    @property
    def desc(self) -> str:
        return "int"

    def __str__(self) -> str:
        return "int"


class TypeSimpleBoolNode(TypeNode):
    @property
    def desc(self) -> str:
        return "bool"

    def __str__(self) -> str:
        return "bool"


class TypeSimpleStringNode(TypeNode):
    @property
    def desc(self) -> str:
        return "string"

    def __str__(self) -> str:
        return "string"


class TypeSimpleDoubleNode(TypeNode):
    @property
    def desc(self) -> str:
        return "double"

    def __str__(self) -> str:
        return "double"


class TypeSimpleVoidNode(TypeNode):
    @property
    def desc(self) -> str:
        return "void"

    def __str__(self) -> str:
        return "void"


class TypeCustomNode(TypeNode):
    def __init__(self, type_name: IdentNode | str):
        super().__init__()
        self.type_name = type_name.name if isinstance(type_name, IdentNode) else str(type_name)

    @property
    def desc(self) -> str:
        return self.type_name

    def __str__(self) -> str:
        return self.type_name


class TypeArrNode(TypeNode):
    def __init__(self, item_type: TypeNode):
        super().__init__()
        self.item_type = item_type

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.item_type,)

    @property
    def desc(self) -> str:
        return f"{self.item_type}[]"

    def __str__(self) -> str:
        return self.desc


class Assign(Enum):
    ASSIGN = "="
    ASSIGN_ADD = "+="
    ASSIGN_SUB = "-="
    ASSIGN_MUL = "*="
    ASSIGN_DIV = "/="
    ASSIGN_IDV = "//="
    ASSIGN_MOD = "%="


class AssignNode(AstNode):
    def __init__(self, assignment: Assign, dest: AstNode, src: AstNode):
        super().__init__()
        self.assignment = assignment
        self.dest = dest
        self.src = src

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.dest, self.src

    def __str__(self) -> str:
        return self.assignment.value


class CallArgListNode(AstNode):
    def __init__(self, *args: AstNode):
        super().__init__()
        self.args = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return tuple(self.args)

    def __str__(self) -> str:
        return "args"


class FuncCallNode(AstNode):
    def __init__(self, entity: AstNode, call_arg: CallArgListNode | None = None):
        super().__init__()
        self.entity = entity
        self.call_arg = call_arg or CallArgListNode()

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.entity, self.call_arg)

    def __str__(self) -> str:
        return f"call {self.entity}"


class ArraySubscrNode(AstNode):
    def __init__(self, entity: AstNode, index: AstNode):
        super().__init__()
        self.entity = entity
        self.index = index

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.entity, self.index

    def __str__(self) -> str:
        return "[]"


class VarDeclNode(AstNode):
    pass


class VarDeclSimpleNode(VarDeclNode):
    def __init__(self, name: IdentNode):
        super().__init__()
        self.name = name

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.name,)

    def __str__(self) -> str:
        return f"decl {self.name}"


class VarDeclArrayNode(VarDeclNode):
    def __init__(self, name: IdentNode):
        super().__init__()
        self.name = name

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.name,)

    def __str__(self) -> str:
        return f"decl {self.name}[]"


class VarInitNode(VarDeclNode):
    def __init__(self, name: IdentNode, value: AstNode):
        super().__init__()
        self.name = name
        self.value = value

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.name, self.value

    def __str__(self) -> str:
        return f"init {self.name}"


class VarInitArrayNode(VarDeclNode):
    def __init__(self, name: IdentNode, value: AstNode):
        super().__init__()
        self.name = name
        self.value = value

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.name, self.value

    def __str__(self) -> str:
        return f"init {self.name}[]"


class CreateVarNode(AstNode):
    def __init__(self, type_: TypeNode, *var_decls: VarDeclNode):
        super().__init__()
        self.type = type_
        self.var_decls = var_decls[0] if len(var_decls) == 1 and isinstance(var_decls[0], tuple) else var_decls

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.type, *self.var_decls)

    def __str__(self) -> str:
        return "create_var"


class StmtNode(AstNode):
    pass


class StmtListNode(StmtNode):
    def __init__(self, *stmts: AstNode):
        super().__init__()
        self.stmts = stmts[0] if len(stmts) == 1 and isinstance(stmts[0], tuple) else stmts
        self.program = False

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return tuple(self.stmts)

    def __str__(self) -> str:
        return "..."


class StmtBreakNode(StmtNode):
    def __str__(self) -> str:
        return "break"


class StmtContinueNode(StmtNode):
    def __str__(self) -> str:
        return "continue"


class StmtReturnNode(StmtNode):
    def __init__(self, value: AstNode | None = None):
        super().__init__()
        self.value = value

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return () if self.value is None else (self.value,)

    def __str__(self) -> str:
        return "return"


class TernaryNode(AstNode):
    def __init__(self, condition: AstNode, branch1: AstNode, branch2: AstNode):
        super().__init__()
        self.condition = condition
        self.branch1 = branch1
        self.branch2 = branch2

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.condition, self.branch1, self.branch2

    def __str__(self) -> str:
        return "?:"


class AccessNode(AstNode):
    def __init__(self, value: AstNode, member: IdentNode):
        super().__init__()
        self.value = value
        self.member = member

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.value, self.member

    def __str__(self) -> str:
        return "."


class BinOp(Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    IDV = "//"
    MOD = "%"
    COMP_LT = "<"
    COMP_GT = ">"
    COMP_LE = "<="
    COMP_GE = ">="
    COMP_EQ = "=="
    COMP_NQ = "!="
    LOGIC_AND = "&&"
    LOGIC_OR = "||"

    def __str__(self) -> str:
        return self.value


class BinOpNode(AstNode):
    def __init__(self, op: BinOp, arg1: AstNode, arg2: AstNode):
        super().__init__()
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.arg1, self.arg2

    def __str__(self) -> str:
        return self.op.value


class UnoOp(Enum):
    UNARY_INC = "+"
    UNARY_DEC = "-"
    PREFIX_INC = "++()"
    PREFIX_DEC = "--()"
    POSTFIX_INC = "()++"
    POSTFIX_DEC = "()--"
    LOGIC_NOT = "!"

    def __str__(self) -> str:
        return self.value


class UnoOpNode(AstNode):
    def __init__(self, op: UnoOp, arg1: AstNode):
        super().__init__()
        self.op = op
        self.arg1 = arg1

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.arg1,)

    def __str__(self) -> str:
        return self.op.value


class ConditionIfNode(AstNode):
    def __init__(self, condition: AstNode, *branches: AstNode):
        super().__init__()
        self.condition = condition
        self.branches = branches

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.condition, *self.branches)

    def __str__(self) -> str:
        return "if"


class ConditionWhileNode(AstNode):
    def __init__(self, condition: AstNode, branch: AstNode):
        super().__init__()
        self.condition = condition
        self.branch = branch

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.condition, self.branch

    def __str__(self) -> str:
        return "while"


class ConditionDoWhileNode(AstNode):
    def __init__(self, branch: AstNode, condition: AstNode):
        super().__init__()
        self.branch = branch
        self.condition = condition

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.branch, self.condition

    def __str__(self) -> str:
        return "do-while"


class ForInitNode(StmtNode):
    def __str__(self) -> str:
        return "empty init"


class ForCondNode(StmtNode):
    def __str__(self) -> str:
        return "empty cond"


class ForNextNode(StmtNode):
    def __str__(self) -> str:
        return "empty next"


class ConditionForNode(AstNode):
    def __init__(self, init: AstNode, condition: AstNode, change: AstNode, body: AstNode):
        super().__init__()
        self.init = init
        self.condition = condition
        self.change = change
        self.body = body

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.init, self.condition, self.change, self.body

    def __str__(self) -> str:
        return "for"


class StructDefNode(StmtNode):
    def __init__(self, name: IdentNode, body: StmtListNode):
        super().__init__()
        self.name = name
        self.body = body

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.body,)

    def __str__(self) -> str:
        return f"struct {self.name}"


class ParamDeclNode(AstNode):
    def __init__(self, type_: TypeNode, ident: IdentNode):
        super().__init__()
        self.type = type_
        self.ident = ident

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.type, self.ident

    def __str__(self) -> str:
        return "param"


class ArrayParamDeclNode(AstNode):
    def __init__(self, type_: TypeNode, ident: IdentNode):
        super().__init__()
        self.type = type_
        self.ident = ident

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.type, self.ident

    def __str__(self) -> str:
        return "param[]"


class ParamListNode(AstNode):
    def __init__(self, *param_decls: AstNode):
        super().__init__()
        self.param_decls = param_decls[0] if len(param_decls) == 1 and isinstance(param_decls[0], tuple) else param_decls

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return tuple(self.param_decls)

    def __str__(self) -> str:
        return "params"


class FuncDefNode(StmtNode):
    def __init__(self, return_type: TypeNode, func_name: IdentNode, params: ParamListNode | None, body: StmtListNode):
        super().__init__()
        self.return_type = return_type
        self.func_name = func_name
        self.params = params or ParamListNode()
        self.body = body

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return self.return_type, self.params, self.body

    def __str__(self) -> str:
        return "func def"


class TypeConvertNode(AstNode):
    def __init__(self, value: AstNode, type_: "TypeDesc"):
        super().__init__()
        self.value = value
        self.type = type_
        self.node_type = type_

    @property
    def childs(self) -> Tuple[AstNode, ...]:
        return (self.value,)

    def __str__(self) -> str:
        return f"({self.type})"
