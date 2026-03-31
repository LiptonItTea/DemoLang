from abc import ABC
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Sequence, Iterable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from semantic import TypeDesc, IdentScope, IdentDesc, SemanticChecker  # noqa


def ast_dataclass(cls, **kwargs):
    """ Специальная версия dataclass без repr """
    return dataclass(cls, repr=False, **kwargs)  # noqa


class AstNode(ABC):
    """ Базовый абстрактный класс узла AST-дерева """

    # действие, которое выполняется при создании каждого узла, если задано
    init_action: Callable[['AstNode'], None] = None
    row: int = None
    col: int = None
    node_type: 'TypeDesc' = None
    node_ident: 'IdentDesc' = None

    @property
    def children(self) -> Sequence['AstNode']:
        """ Возвращает список вложенных узлов (логика по умолчанию, когда view_node возвращает None) """
        children: list[AstNode] = []
        for k, v in self.__dict__.items():
            if isinstance(v, AstNode):
                children.append(v)
            if isinstance(v, Iterable):
                for item in v:
                    if isinstance(item, AstNode):
                        children.append(item)
        return children

    def __str__(self) -> str:
        name = None

        for field in ('name', 'op', 'type', 'desc'):  # поля в классах AstNode для представления узла в виде строки
            if hasattr(self, field):
                field = getattr(self, field)
                if not field:
                    continue
                if hasattr(field, 'value'):
                    name = str(getattr(field, 'value'))
                elif isinstance(field, AstNode):
                    name = str(field)
                else:
                    name = str(field)
        if not name:
            name = self.__class__.__name__
            if name.endswith('Node'):
                name = name[:-4].lower()
            if name.endswith('list'):
                name = f'{name[:-4]}[]'

        return name

    """ Нужно для модуля visitor при реализации методов класса SemanticChecker в модуле semantic """
    def semantic_check(self, checker: 'SemanticChecker', scope: 'IdentScope') -> None:
        checker.semantic_check(self, scope)


class ExprNode(AstNode, ABC):
    pass


class ValueNode(ExprNode, ABC):
    pass


class StmtNode(AstNode, ABC):
    pass


@ast_dataclass
class LiteralNode(ExprNode):
    """ Класс для представления в AST-дереве литералов (числа, строки, логическое значение) """
    literal: str
    value: Any

    def __init__(self, literal: str) -> None:
        self.literal = str(literal)
        if literal in ('true', 'false'):
            self.value = bool(literal)
        else:
            self.value = eval(literal)


@ast_dataclass
class IdentNode(ExprNode):
    name: str


@ast_dataclass
class TypeNode(ExprNode):
    """ Класс для представления в AST-дереве типов данный
        (при появлении составных типов данных должен быть расширен)
    """
    desc: str
    type: 'TypeDesc' = None


class IncDecOp(Enum):
    PREFIX_INC = '++()'
    PREFIX_DEC = '--()'
    SUFFIX_INC = '()++'
    SUFFIX_DEC = '()--'

    def __str__(self):
        return self.value


@ast_dataclass
class IncDecNode(AstNode):
    op: IncDecOp
    var: IdentNode


class UnOp(Enum):
    NOT = '!'
    PLUS = '+'
    MINUS = '-'

    def __str__(self):
        return self.value


@ast_dataclass
class UnOpNode(ExprNode):
    op: UnOp
    arg: ExprNode


class BinOp(Enum):
    ADD = '+'
    SUB = '-'
    MUL = '*'
    DIV = '/'
    MOD = '%'
    GT = '>'
    GE = '>='
    LT = '<'
    LE = '<='
    EQ = '=='
    NE = '!='
    BIT_AND = '&'
    BIT_OR = '|'
    LOGIC_OR = '||'
    LOGIC_AND = '&&'

    def __str__(self):
        return self.value


@ast_dataclass
class BinOpNode(ExprNode):
    op: BinOp
    arg1: ExprNode
    arg2: ExprNode


@ast_dataclass
class AssignNode(ExprNode, StmtNode):
    var: ExprNode
    value: ExprNode


@ast_dataclass
class VarsDeclNode(StmtNode):
    type: TypeNode
    vars: Sequence[ExprNode]

    def __init__(self, type_: TypeNode, *vars_: ExprNode) -> None:
        self.type = type_
        # на случай, если vars будут переданы в виде одного списка
        self.vars = vars_[0] if len(vars_) == 1 and isinstance(vars_[0], Sequence) else vars_


@ast_dataclass
class CallNode(ExprNode, StmtNode):
    name: IdentNode
    params: Sequence[ExprNode]

    def __init__(self, name: IdentNode, *params: ExprNode) -> None:
        self.name = name
        # на случай, если params будут переданы в виде одного списка
        self.params = params[0] if len(params) == 1 and isinstance(params[0], Sequence) else params


@ast_dataclass
class IfNode(StmtNode):
    cond: ExprNode
    then_stmt: StmtNode
    else_stmt: StmtNode = None

    def __init__(self, cond: ExprNode, then_stmt: StmtNode, else_stmt: StmtNode = None) -> None:
        self.cond = cond
        # в моей реализации парсера (Lark) это не нужно, так как параметры всегда не null, но на всякий случай
        self.then_stmt = then_stmt or StmtListNode()
        self.else_stmt = else_stmt


@ast_dataclass
class WhileNode(StmtNode):
    cond: ExprNode
    body: StmtNode

    def __init__(self, cond: ExprNode, body: StmtNode) -> None:
        self.cond = cond
        # в моей реализации парсера (Lark) это не нужно, так как параметры всегда не null, но на всякий случай
        self.body = body or StmtListNode()


@ast_dataclass
class ForNode(StmtNode):
    init: StmtNode
    cond: ExprNode
    next: StmtNode
    body: StmtNode

    def __init__(self, init: StmtNode, cond: ExprNode, next_: StmtNode, body: StmtNode) -> None:
        # в моей реализации парсера (Lark) это не нужно, так как параметры всегда не null, но на всякий случай
        self.init = init or StmtListNode()
        self.cond = cond or LiteralNode('true')
        self.next = next_ or StmtListNode()
        self.body = body or StmtListNode()


@ast_dataclass
class BreakNode(StmtNode):
    pass


@ast_dataclass
class ContinueNode(StmtNode):
    pass


@ast_dataclass
class ReturnNode(StmtNode):
    value: ExprNode = None


@ast_dataclass
class StmtListNode(StmtNode):
    stmts: Sequence[StmtNode]
    program: bool = False

    def __init__(self, *stmts: StmtNode) -> None:
        # на случай, если params будут переданы в виде одного списка
        self.stmts = stmts[0] if len(stmts) == 1 and isinstance(stmts[0], Sequence) else stmts


@ast_dataclass
class FuncNode(StmtNode):
    type: TypeNode
    name: IdentNode
    params: list[VarsDeclNode]
    body: StmtNode


@ast_dataclass
class TypeConvertNode(ExprNode):
    """ Класс для представления в AST-дереве операций конвертации типов данных """
    value: ExprNode
    type: 'TypeDesc'

    def __init__(self, expr: ExprNode, type_: 'TypeDesc') -> None:
        self.value = expr
        self.type = type_
        self.node_type = type_
