from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from . import visitor
from .ast import *
from .errors import SemanticException


class BaseType(Enum):
    VOID = "void"
    INT = "int"
    DOUBLE = "double"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    CHAR = "char"

    def __str__(self) -> str:
        return self.value


VOID, INT, DOUBLE, FLOAT, BOOL, STRING, CHAR = (
    BaseType.VOID,
    BaseType.INT,
    BaseType.DOUBLE,
    BaseType.FLOAT,
    BaseType.BOOL,
    BaseType.STRING,
    BaseType.CHAR,
)


class TypeDesc:
    VOID: "TypeDesc"
    INT: "TypeDesc"
    DOUBLE: "TypeDesc"
    FLOAT: "TypeDesc"
    BOOL: "TypeDesc"
    STRING: "TypeDesc"
    CHAR: "TypeDesc"

    def __init__(
        self,
        base_type: BaseType | None = None,
        custom_name: str | None = None,
        array_item_type: "TypeDesc | None" = None,
        return_type: "TypeDesc | None" = None,
        params: Sequence["TypeDesc"] | None = None,
    ) -> None:
        self.base_type = base_type
        self.custom_name = custom_name
        self.array_item_type = array_item_type
        self.return_type = return_type
        self.params = tuple(params or ())

    @property
    def func(self) -> bool:
        return self.return_type is not None

    @property
    def is_array(self) -> bool:
        return self.array_item_type is not None

    @property
    def is_custom(self) -> bool:
        return self.custom_name is not None and not self.func and not self.is_array

    @property
    def is_simple(self) -> bool:
        return not self.func and not self.is_array and not self.is_custom

    @staticmethod
    def from_base_type(base_type: BaseType) -> "TypeDesc":
        return getattr(TypeDesc, base_type.name)

    @staticmethod
    def custom(name: str) -> "TypeDesc":
        return TypeDesc(custom_name=name)

    @staticmethod
    def array_of(item_type: "TypeDesc") -> "TypeDesc":
        return TypeDesc(array_item_type=item_type)

    @staticmethod
    def function(return_type: "TypeDesc", params: Sequence["TypeDesc"]) -> "TypeDesc":
        return TypeDesc(return_type=return_type, params=tuple(params))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypeDesc):
            return False
        return (
            self.base_type == other.base_type
            and self.custom_name == other.custom_name
            and self.array_item_type == other.array_item_type
            and self.return_type == other.return_type
            and tuple(self.params) == tuple(other.params)
        )

    def __str__(self) -> str:
        if self.func:
            params = ", ".join(str(param) for param in self.params)
            return f"{self.return_type} ({params})"
        if self.is_array:
            return f"{self.array_item_type}[]"
        if self.is_custom:
            return self.custom_name
        return str(self.base_type)


for base_type in BaseType:
    setattr(TypeDesc, base_type.name, TypeDesc(base_type=base_type))


@dataclass
class StructDesc:
    name: str
    fields: dict[str, "IdentDesc"]

    def __str__(self) -> str:
        return f"struct {self.name}"


class ScopeType(Enum):
    GLOBAL = "global"
    PARAM = "param"
    LOCAL = "local"
    FIELD = "field"

    def __str__(self) -> str:
        return self.value


class IdentDesc:
    def __init__(
        self,
        name: str,
        type_: TypeDesc,
        scope: ScopeType = ScopeType.GLOBAL,
        index: int = 0,
        variadic: bool = False,
    ) -> None:
        self.name = name
        self.type = type_
        self.scope = scope
        self.index = index
        self.built_in = False
        self.variadic = variadic

    def __str__(self) -> str:
        result = f"{self.type}, {self.scope}"
        if self.built_in:
            result += ", built-in"
        if self.variadic:
            result += ", variadic"
        elif not self.type.func and self.scope != ScopeType.FIELD:
            result += f", {self.index}"
        return result


class IdentScope:
    def __init__(self, parent: "IdentScope | None" = None) -> None:
        self.parent = parent
        self.idents: dict[str, IdentDesc] = {}
        self.func: IdentDesc | None = None
        self.types: dict[str, StructDesc] = {} if parent is None else {}
        self.var_index = 0
        self.param_index = 0
        self.loop_depth = 0

    @property
    def curr_global(self) -> "IdentScope":
        scope = self
        while scope.parent:
            scope = scope.parent
        return scope

    @property
    def curr_func_scope(self) -> "IdentScope | None":
        scope = self
        while scope and scope.func is None:
            scope = scope.parent
        return scope

    @property
    def in_loop(self) -> bool:
        scope = self
        while scope:
            if scope.loop_depth > 0:
                return True
            scope = scope.parent
        return False

    def add_type(self, struct_desc: StructDesc) -> StructDesc:
        global_scope = self.curr_global
        if struct_desc.name in global_scope.types:
            raise SemanticException(f"Тип {struct_desc.name} уже объявлен")
        global_scope.types[struct_desc.name] = struct_desc
        return struct_desc

    def get_type(self, name: str) -> StructDesc | None:
        return self.curr_global.types.get(name)

    def add_ident(self, ident: IdentDesc) -> IdentDesc:
        if ident.scope not in (ScopeType.PARAM, ScopeType.FIELD):
            ident.scope = ScopeType.LOCAL if self.parent is not None else ScopeType.GLOBAL

        if ident.name in self.idents:
            raise SemanticException(f"Идентификатор {ident.name} уже объявлен")

        if not ident.type.func and ident.scope != ScopeType.FIELD:
            if ident.scope == ScopeType.PARAM:
                func_scope = self.curr_func_scope or self
                ident.index = func_scope.param_index
                func_scope.param_index += 1
            else:
                owner_scope = self.curr_func_scope or self.curr_global
                ident.index = owner_scope.var_index
                owner_scope.var_index += 1

        self.idents[ident.name] = ident
        return ident

    def get_ident(self, name: str) -> IdentDesc | None:
        scope = self
        while scope:
            ident = scope.idents.get(name)
            if ident is not None:
                return ident
            scope = scope.parent
        return None


STRINGLIKE_BASES = {STRING, CHAR}
NUMERIC_BASES = {INT, DOUBLE, FLOAT, CHAR}


def semantic_error(node: AstNode | None, message: str) -> None:
    if node is None:
        raise SemanticException(message)
    raise SemanticException(message, node.row, node.col)


def is_numeric_type(type_: TypeDesc) -> bool:
    return type_.is_simple and type_.base_type in NUMERIC_BASES


def is_stringlike_type(type_: TypeDesc) -> bool:
    return type_.is_simple and type_.base_type in STRINGLIKE_BASES


def can_type_convert_to(from_type: TypeDesc, to_type: TypeDesc) -> bool:
    if from_type == to_type:
        return True

    if from_type.func or to_type.func or from_type.is_array or to_type.is_array:
        return False

    if from_type.is_custom or to_type.is_custom:
        return False

    if to_type == TypeDesc.STRING and from_type.base_type in (INT, DOUBLE, FLOAT, BOOL, CHAR):
        return True
    if from_type == TypeDesc.INT and to_type in (TypeDesc.DOUBLE, TypeDesc.FLOAT, TypeDesc.BOOL, TypeDesc.CHAR):
        return True
    if from_type == TypeDesc.CHAR and to_type in (TypeDesc.INT, TypeDesc.STRING):
        return True
    if from_type == TypeDesc.DOUBLE and to_type == TypeDesc.STRING:
        return True
    if from_type == TypeDesc.FLOAT and to_type == TypeDesc.STRING:
        return True
    if from_type == TypeDesc.BOOL and to_type == TypeDesc.STRING:
        return True
    return False


def type_convert(
    expr: AstNode,
    type_: TypeDesc,
    except_node: AstNode | None = None,
    comment: str | None = None,
) -> AstNode:
    if expr.node_type is None:
        semantic_error(except_node or expr, "Тип выражения не определен")
    if expr.node_type == type_:
        return expr
    if can_type_convert_to(expr.node_type, type_):
        return TypeConvertNode(expr, type_)

    suffix = f" ({comment})" if comment else ""
    semantic_error(except_node or expr, f"Тип {expr.node_type}{suffix} не конвертируется в {type_}")


def resolve_type(node: TypeNode, scope: IdentScope) -> TypeDesc:
    if isinstance(node, TypeSimpleCharNode):
        result = TypeDesc.CHAR
    elif isinstance(node, TypeSimpleIntNode):
        result = TypeDesc.INT
    elif isinstance(node, TypeSimpleBoolNode):
        result = TypeDesc.BOOL
    elif isinstance(node, TypeSimpleStringNode):
        result = TypeDesc.STRING
    elif isinstance(node, TypeSimpleDoubleNode):
        result = TypeDesc.DOUBLE
    elif isinstance(node, TypeSimpleFloatNode):
        result = TypeDesc.FLOAT
    elif isinstance(node, TypeSimpleVoidNode):
        result = TypeDesc.VOID
    elif isinstance(node, TypeCustomNode):
        if scope.get_type(node.type_name) is None:
            semantic_error(node, f"Неизвестный тип {node.type_name}")
        result = TypeDesc.custom(node.type_name)
    elif isinstance(node, TypeArrNode):
        result = TypeDesc.array_of(resolve_type(node.item_type, scope))
    else:
        semantic_error(node, f"Неизвестное описание типа {node}")

    node.type = result
    node.node_type = result
    return result


def build_array_type(base_type: TypeDesc, dimensions: int) -> TypeDesc:
    result = base_type
    for _ in range(dimensions):
        result = TypeDesc.array_of(result)
    return result


def get_assignment_target_type(node: AstNode, scope: IdentScope) -> TypeDesc:
    node.semantic_check(SemanticChecker(), scope)
    if node.node_type is None or node.node_type.func:
        semantic_error(node, "Некорректная цель присваивания")
    return node.node_type


def ensure_assignable(node: AstNode) -> None:
    if not isinstance(node, (IdentNode, ArraySubscrNode, AccessNode)):
        semantic_error(node, "Левая часть выражения должна быть изменяемой")


def convert_numeric(expr: AstNode, target: TypeDesc) -> AstNode:
    if expr.node_type == target:
        return expr
    if expr.node_type == TypeDesc.CHAR and target in (TypeDesc.INT, TypeDesc.DOUBLE, TypeDesc.FLOAT):
        return type_convert(expr, TypeDesc.INT if target == TypeDesc.INT else TypeDesc.DOUBLE if target == TypeDesc.DOUBLE else TypeDesc.FLOAT)
    if expr.node_type == TypeDesc.INT and target == TypeDesc.DOUBLE:
        return type_convert(expr, TypeDesc.DOUBLE)
    if expr.node_type == TypeDesc.INT and target == TypeDesc.FLOAT:
        return type_convert(expr, TypeDesc.FLOAT)
    return expr


def align_numeric_pair(left: AstNode, right: AstNode, node: AstNode, *, int_only: bool = False) -> tuple[AstNode, AstNode, TypeDesc]:
    if not is_numeric_type(left.node_type) or not is_numeric_type(right.node_type):
        semantic_error(node, f"Операция неприменима к типам ({left.node_type}, {right.node_type})")

    if int_only:
        left = type_convert(left, TypeDesc.INT, node)
        right = type_convert(right, TypeDesc.INT, node)
        return left, right, TypeDesc.INT

    target = TypeDesc.DOUBLE if TypeDesc.DOUBLE in (left.node_type, right.node_type) else TypeDesc.FLOAT if TypeDesc.FLOAT in (left.node_type, right.node_type) else TypeDesc.INT
    left = convert_numeric(left, target)
    right = convert_numeric(right, target)
    if left.node_type == TypeDesc.CHAR:
        left = type_convert(left, target, node)
    if right.node_type == TypeDesc.CHAR:
        right = type_convert(right, target, node)
    return left, right, target


def resolve_binary(node: BinOpNode) -> tuple[AstNode, AstNode, TypeDesc]:
    left = node.arg1
    right = node.arg2

    if node.op == BinOp.ADD and (is_stringlike_type(left.node_type) or is_stringlike_type(right.node_type)):
        left = type_convert(left, TypeDesc.STRING, node)
        right = type_convert(right, TypeDesc.STRING, node)
        return left, right, TypeDesc.STRING

    if node.op in (BinOp.ADD, BinOp.SUB, BinOp.MUL, BinOp.DIV):
        left, right, result = align_numeric_pair(left, right, node)
        return left, right, result

    if node.op in (BinOp.IDV, BinOp.MOD):
        left, right, _ = align_numeric_pair(left, right, node, int_only=True)
        return left, right, TypeDesc.INT

    if node.op in (BinOp.COMP_LT, BinOp.COMP_GT, BinOp.COMP_LE, BinOp.COMP_GE):
        if is_stringlike_type(left.node_type) and is_stringlike_type(right.node_type):
            left = type_convert(left, TypeDesc.STRING, node)
            right = type_convert(right, TypeDesc.STRING, node)
            return left, right, TypeDesc.BOOL
        left, right, _ = align_numeric_pair(left, right, node)
        return left, right, TypeDesc.BOOL

    if node.op in (BinOp.COMP_EQ, BinOp.COMP_NQ):
        if left.node_type == right.node_type:
            return left, right, TypeDesc.BOOL
        if is_stringlike_type(left.node_type) and is_stringlike_type(right.node_type):
            left = type_convert(left, TypeDesc.STRING, node)
            right = type_convert(right, TypeDesc.STRING, node)
            return left, right, TypeDesc.BOOL
        if is_numeric_type(left.node_type) and is_numeric_type(right.node_type):
            left, right, _ = align_numeric_pair(left, right, node)
            return left, right, TypeDesc.BOOL
        if can_type_convert_to(left.node_type, right.node_type):
            left = type_convert(left, right.node_type, node)
            return left, right, TypeDesc.BOOL
        if can_type_convert_to(right.node_type, left.node_type):
            right = type_convert(right, left.node_type, node)
            return left, right, TypeDesc.BOOL
        semantic_error(node, f"Оператор {node.op} не применим к типам ({left.node_type}, {right.node_type})")

    if node.op in (BinOp.LOGIC_AND, BinOp.LOGIC_OR):
        left = type_convert(left, TypeDesc.BOOL, node, "логическое выражение")
        right = type_convert(right, TypeDesc.BOOL, node, "логическое выражение")
        return left, right, TypeDesc.BOOL

    semantic_error(node, f"Неизвестный бинарный оператор {node.op}")


def resolve_compound_assignment(dest: AstNode, src: AstNode, op: Assign, node: AssignNode) -> AstNode:
    op_map = {
        Assign.ASSIGN_ADD: BinOp.ADD,
        Assign.ASSIGN_SUB: BinOp.SUB,
        Assign.ASSIGN_MUL: BinOp.MUL,
        Assign.ASSIGN_DIV: BinOp.DIV,
        Assign.ASSIGN_IDV: BinOp.IDV,
        Assign.ASSIGN_MOD: BinOp.MOD,
    }
    temp = BinOpNode(op_map[op], dest, src)
    temp.row = node.row
    temp.col = node.col
    temp.arg1.node_type = dest.node_type
    temp.arg2.node_type = src.node_type
    left, right, result_type = resolve_binary(temp)
    _ = left, right
    if result_type != dest.node_type:
        src = type_convert(src, dest.node_type, node, "присваиваемое значение")
    return src


class SemanticChecker:
    @visitor.on("AstNode")
    def semantic_check(self, AstNode, scope: IdentScope):  # noqa
        pass

    @visitor.when(AstNode)
    def semantic_check(self, node: AstNode, scope: IdentScope):
        for child in node.childs:
            child.semantic_check(self, scope)

    @visitor.when(NumNode)
    def semantic_check(self, node: NumNode, scope: IdentScope):
        node.node_type = TypeDesc.FLOAT if isinstance(node.value, float) else TypeDesc.INT

    @visitor.when(StringNode)
    def semantic_check(self, node: StringNode, scope: IdentScope):
        node.node_type = TypeDesc.STRING

    @visitor.when(SqStringNode)
    def semantic_check(self, node: SqStringNode, scope: IdentScope):
        node.node_type = TypeDesc.CHAR if len(node.value) == 1 else TypeDesc.STRING

    @visitor.when(IdentNode)
    def semantic_check(self, node: IdentNode, scope: IdentScope):
        ident = scope.get_ident(node.name)
        if ident is None:
            semantic_error(node, f"Идентификатор {node.name} не найден")
        node.node_type = ident.type
        node.node_ident = ident

    @visitor.when(TypeNode)
    def semantic_check(self, node: TypeNode, scope: IdentScope):
        resolve_type(node, scope)

    @visitor.when(TypeConvertNode)
    def semantic_check(self, node: TypeConvertNode, scope: IdentScope):
        node.value.semantic_check(self, scope)
        node.node_type = node.type

    @visitor.when(ArrayAllocDimNode)
    def semantic_check(self, node: ArrayAllocDimNode, scope: IdentScope):
        if node.size is not None:
            node.size.semantic_check(self, scope)
            node.size = type_convert(node.size, TypeDesc.INT, node, "размер массива")
        node.node_type = TypeDesc.VOID

    @visitor.when(ArrayAllocNode)
    def semantic_check(self, node: ArrayAllocNode, scope: IdentScope):
        base_type = resolve_type(node.base_type, scope)
        if base_type == TypeDesc.VOID:
            semantic_error(node.base_type, "Нельзя создавать массив элементов типа void")

        saw_sized = False
        saw_empty = False
        for dim in node.dims:
            if dim.size is None:
                if not saw_sized:
                    semantic_error(dim, "Первая размерность массива должна быть задана")
                saw_empty = True
            else:
                if saw_empty:
                    semantic_error(dim, "Пустые размерности массива могут идти только в конце")
                saw_sized = True
            dim.semantic_check(self, scope)

        node.node_type = build_array_type(base_type, len(node.dims))

    @visitor.when(CallArgListNode)
    def semantic_check(self, node: CallArgListNode, scope: IdentScope):
        for arg in node.args:
            arg.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(ArraySubscrNode)
    def semantic_check(self, node: ArraySubscrNode, scope: IdentScope):
        node.entity.semantic_check(self, scope)
        node.index.semantic_check(self, scope)
        node.index = type_convert(node.index, TypeDesc.INT, node, "индекс массива")

        if node.entity.node_type.is_array:
            node.node_type = node.entity.node_type.array_item_type
        elif node.entity.node_type == TypeDesc.STRING:
            node.node_type = TypeDesc.CHAR
        else:
            semantic_error(node, f"Индексирование неприменимо к типу {node.entity.node_type}")

    @visitor.when(AccessNode)
    def semantic_check(self, node: AccessNode, scope: IdentScope):
        node.value.semantic_check(self, scope)
        if not node.value.node_type.is_custom:
            semantic_error(node, f"Операция доступа по полю неприменима к типу {node.value.node_type}")

        struct_desc = scope.get_type(node.value.node_type.custom_name)
        if struct_desc is None:
            semantic_error(node, f"Неизвестный тип {node.value.node_type.custom_name}")

        field = struct_desc.fields.get(node.member.name)
        if field is None:
            semantic_error(node.member, f"Поле {node.member.name} не найдено в типе {struct_desc.name}")

        node.member.node_type = field.type
        node.member.node_ident = field
        node.node_type = field.type
        node.node_ident = field

    @visitor.when(FuncCallNode)
    def semantic_check(self, node: FuncCallNode, scope: IdentScope):
        node.entity.semantic_check(self, scope)
        func_ident = node.entity.node_ident
        func_type = node.entity.node_type

        if func_type is None or not func_type.func:
            semantic_error(node, f"Выражение {node.entity} не является функцией")

        args = list(node.call_arg.args)
        for arg in args:
            arg.semantic_check(self, scope)

        if func_ident and func_ident.variadic:
            converted = []
            for arg in args:
                if arg.node_type.func:
                    semantic_error(arg, "Функцию нельзя передавать в print/println")
                if arg.node_type != TypeDesc.STRING:
                    if can_type_convert_to(arg.node_type, TypeDesc.STRING):
                        arg = type_convert(arg, TypeDesc.STRING, node)
                    elif arg.node_type != TypeDesc.STRING:
                        semantic_error(arg, f"Тип {arg.node_type} нельзя вывести как строку")
                converted.append(arg)
            node.call_arg.args = tuple(converted)
        else:
            if len(func_type.params) != len(args):
                semantic_error(
                    node,
                    f"Кол-во аргументов {node.entity} не совпадает "
                    f"(ожидалось {len(func_type.params)}, передано {len(args)})",
                )

            converted = []
            for arg, expected in zip(args, func_type.params):
                converted.append(type_convert(arg, expected, node, "аргумент функции"))
            node.call_arg.args = tuple(converted)

        node.node_type = func_type.return_type
        node.node_ident = func_ident

    @visitor.when(UnoOpNode)
    def semantic_check(self, node: UnoOpNode, scope: IdentScope):
        node.arg1.semantic_check(self, scope)

        if node.op == UnoOp.LOGIC_NOT:
            node.arg1 = type_convert(node.arg1, TypeDesc.BOOL, node, "логическое выражение")
            node.node_type = TypeDesc.BOOL
            return

        if node.op in (UnoOp.UNARY_INC, UnoOp.UNARY_DEC):
            if not is_numeric_type(node.arg1.node_type):
                semantic_error(node, f"Оператор {node.op} не применим к типу {node.arg1.node_type}")
            if node.arg1.node_type == TypeDesc.CHAR:
                node.arg1 = type_convert(node.arg1, TypeDesc.INT, node)
                node.node_type = TypeDesc.INT
            else:
                node.node_type = node.arg1.node_type
            return

        ensure_assignable(node.arg1)
        if not is_numeric_type(node.arg1.node_type):
            semantic_error(node, f"Оператор {node.op} можно применить только к числовым lvalue")
        node.node_type = node.arg1.node_type if node.arg1.node_type != TypeDesc.CHAR else TypeDesc.INT

    @visitor.when(BinOpNode)
    def semantic_check(self, node: BinOpNode, scope: IdentScope):
        node.arg1.semantic_check(self, scope)
        node.arg2.semantic_check(self, scope)
        node.arg1, node.arg2, node.node_type = resolve_binary(node)

    @visitor.when(TernaryNode)
    def semantic_check(self, node: TernaryNode, scope: IdentScope):
        node.condition.semantic_check(self, scope)
        node.branch1.semantic_check(self, scope)
        node.branch2.semantic_check(self, scope)

        node.condition = type_convert(node.condition, TypeDesc.BOOL, node, "условие")
        if node.branch1.node_type == node.branch2.node_type:
            node.node_type = node.branch1.node_type
            return

        if can_type_convert_to(node.branch1.node_type, node.branch2.node_type):
            node.branch1 = type_convert(node.branch1, node.branch2.node_type, node)
            node.node_type = node.branch2.node_type
            return

        if can_type_convert_to(node.branch2.node_type, node.branch1.node_type):
            node.branch2 = type_convert(node.branch2, node.branch1.node_type, node)
            node.node_type = node.branch1.node_type
            return

        if is_numeric_type(node.branch1.node_type) and is_numeric_type(node.branch2.node_type):
            dummy = BinOpNode(BinOp.ADD, node.branch1, node.branch2)
            dummy.row = node.row
            dummy.col = node.col
            node.branch1, node.branch2, node.node_type = resolve_binary(dummy)
            return

        semantic_error(node, f"Ветки тернарного оператора имеют несовместимые типы ({node.branch1.node_type}, {node.branch2.node_type})")

    @visitor.when(AssignNode)
    def semantic_check(self, node: AssignNode, scope: IdentScope):
        ensure_assignable(node.dest)
        node.dest.semantic_check(self, scope)
        node.src.semantic_check(self, scope)

        if node.assignment == Assign.ASSIGN:
            node.src = type_convert(node.src, node.dest.node_type, node, "присваиваемое значение")
        else:
            node.src = resolve_compound_assignment(node.dest, node.src, node.assignment, node)

        node.node_type = node.dest.node_type

    @visitor.when(CreateVarNode)
    def semantic_check(self, node: CreateVarNode, scope: IdentScope):
        decl_type = resolve_type(node.type, scope)
        if decl_type == TypeDesc.VOID:
            semantic_error(node.type, "Переменные типа void не поддерживаются")

        for decl in node.var_decls:
            curr_type = decl_type

            ident = scope.add_ident(IdentDesc(decl.name.name, curr_type))
            decl.name.node_type = curr_type
            decl.name.node_ident = ident
            decl.node_type = curr_type
            decl.node_ident = ident

            if isinstance(decl, VarInitNode):
                decl.value.semantic_check(self, scope)
                decl.value = type_convert(decl.value, curr_type, decl, "инициализатор")

        node.node_type = TypeDesc.VOID

    @visitor.when(StmtReturnNode)
    def semantic_check(self, node: StmtReturnNode, scope: IdentScope):
        func_scope = scope.curr_func_scope
        if func_scope is None or func_scope.func is None:
            semantic_error(node, "Оператор return может использоваться только внутри функции")

        expected = func_scope.func.type.return_type
        if node.value is None:
            if expected != TypeDesc.VOID:
                semantic_error(node, f"Функция должна вернуть значение типа {expected}")
        else:
            node.value.semantic_check(self, scope)
            node.value = type_convert(node.value, expected, node, "возвращаемое значение")

        node.node_type = TypeDesc.VOID

    @visitor.when(StmtBreakNode)
    def semantic_check(self, node: StmtBreakNode, scope: IdentScope):
        if not scope.in_loop:
            semantic_error(node, "Оператор break может использоваться только внутри цикла")
        node.node_type = TypeDesc.VOID

    @visitor.when(StmtContinueNode)
    def semantic_check(self, node: StmtContinueNode, scope: IdentScope):
        if not scope.in_loop:
            semantic_error(node, "Оператор continue может использоваться только внутри цикла")
        node.node_type = TypeDesc.VOID

    @visitor.when(ConditionIfNode)
    def semantic_check(self, node: ConditionIfNode, scope: IdentScope):
        node.condition.semantic_check(self, scope)
        node.condition = type_convert(node.condition, TypeDesc.BOOL, node, "условие")
        for branch in node.branches:
            branch.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(ConditionWhileNode)
    def semantic_check(self, node: ConditionWhileNode, scope: IdentScope):
        loop_scope = IdentScope(scope)
        loop_scope.loop_depth = 1
        node.condition.semantic_check(self, scope)
        node.condition = type_convert(node.condition, TypeDesc.BOOL, node, "условие")
        node.branch.semantic_check(self, loop_scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(ConditionDoWhileNode)
    def semantic_check(self, node: ConditionDoWhileNode, scope: IdentScope):
        loop_scope = IdentScope(scope)
        loop_scope.loop_depth = 1
        node.branch.semantic_check(self, loop_scope)
        node.condition.semantic_check(self, scope)
        node.condition = type_convert(node.condition, TypeDesc.BOOL, node, "условие")
        node.node_type = TypeDesc.VOID

    @visitor.when(ConditionForNode)
    def semantic_check(self, node: ConditionForNode, scope: IdentScope):
        loop_scope = IdentScope(scope)
        loop_scope.loop_depth = 1

        if not isinstance(node.init, ForInitNode):
            node.init.semantic_check(self, loop_scope)
        if not isinstance(node.condition, ForCondNode):
            node.condition.semantic_check(self, loop_scope)
            node.condition = type_convert(node.condition, TypeDesc.BOOL, node, "условие")
        if not isinstance(node.change, ForNextNode):
            node.change.semantic_check(self, loop_scope)

        node.body.semantic_check(self, IdentScope(loop_scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(ParamDeclNode)
    def semantic_check(self, node: ParamDeclNode, scope: IdentScope):
        node.node_type = resolve_type(node.type, scope)

    @visitor.when(FuncDefNode)
    def semantic_check(self, node: FuncDefNode, scope: IdentScope):
        if scope.parent is not None:
            semantic_error(node, "Объявление функции поддерживается только в глобальной области")

        return_type = resolve_type(node.return_type, scope)
        params: list[TypeDesc] = []
        for param in node.params.param_decls:
            params.append(resolve_type(param.type, scope))

        func_type = TypeDesc.function(return_type, tuple(params))
        func_ident = scope.add_ident(IdentDesc(node.func_name.name, func_type))
        node.func_name.node_type = func_type
        node.func_name.node_ident = func_ident

        func_scope = IdentScope(scope)
        func_scope.func = func_ident

        for param, param_type in zip(node.params.param_decls, params):
            ident = func_scope.add_ident(IdentDesc(param.ident.name, param_type, ScopeType.PARAM))
            param.ident.node_type = param_type
            param.ident.node_ident = ident
            param.node_type = param_type
            param.node_ident = ident

        node.body.semantic_check(self, func_scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(StructDefNode)
    def semantic_check(self, node: StructDefNode, scope: IdentScope):
        if scope.parent is not None:
            semantic_error(node, "Объявление struct поддерживается только в глобальной области")

        struct_desc = StructDesc(node.name.name, {})
        scope.add_type(struct_desc)

        if not isinstance(node.body, StmtListNode):
            body_stmts = [node.body]
        else:
            body_stmts = node.body.stmts

        for stmt in body_stmts:
            if not isinstance(stmt, CreateVarNode):
                semantic_error(stmt, "Внутри struct допускаются только объявления полей")

            field_type = resolve_type(stmt.type, scope)
            if field_type == TypeDesc.VOID:
                semantic_error(stmt.type, "Поле типа void не поддерживается")

            for decl in stmt.var_decls:
                if isinstance(decl, VarInitNode):
                    semantic_error(decl, "Инициализация полей внутри struct не поддерживается")

                current_type = field_type
                if decl.name.name in struct_desc.fields:
                    semantic_error(decl.name, f"Поле {decl.name.name} уже объявлено в struct {struct_desc.name}")

                ident = IdentDesc(decl.name.name, current_type, ScopeType.FIELD)
                struct_desc.fields[decl.name.name] = ident
                decl.name.node_type = current_type
                decl.name.node_ident = ident
                decl.node_type = current_type
                decl.node_ident = ident

        node.node_type = TypeDesc.VOID

    @visitor.when(StmtListNode)
    def semantic_check(self, node: StmtListNode, scope: IdentScope):
        local_scope = scope if node.program else IdentScope(scope)
        for stmt in node.stmts:
            stmt.semantic_check(self, local_scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(ForInitNode)
    def semantic_check(self, node: ForInitNode, scope: IdentScope):
        node.node_type = TypeDesc.VOID

    @visitor.when(ForCondNode)
    def semantic_check(self, node: ForCondNode, scope: IdentScope):
        node.node_type = TypeDesc.VOID

    @visitor.when(ForNextNode)
    def semantic_check(self, node: ForNextNode, scope: IdentScope):
        node.node_type = TypeDesc.VOID


def prepare_global_scope() -> IdentScope:
    scope = IdentScope()

    builtins = (
        IdentDesc("read", TypeDesc.function(TypeDesc.STRING, ())),
        IdentDesc("to_int", TypeDesc.function(TypeDesc.INT, (TypeDesc.STRING,))),
        IdentDesc("to_double", TypeDesc.function(TypeDesc.DOUBLE, (TypeDesc.STRING,))),
        IdentDesc("to_float", TypeDesc.function(TypeDesc.FLOAT, (TypeDesc.STRING,))),
        IdentDesc("print", TypeDesc.function(TypeDesc.VOID, ()), variadic=True),
        IdentDesc("println", TypeDesc.function(TypeDesc.VOID, ()), variadic=True),
    )

    for ident in builtins:
        ident.built_in = True
        scope.add_ident(ident)

    scope.var_index = 0
    return scope


def semantic_check(program: AstNode) -> None:
    checker = SemanticChecker()
    scope = prepare_global_scope()
    checker.semantic_check(program, scope)
