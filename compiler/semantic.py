from . import visitor
from .ast import *
from .errors import SemanticException


class BaseType(Enum):
    """ Перечисление для базовых типов данных """

    VOID = 'void'
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'
    STR = 'string'

    def __str__(self):
        return self.value


VOID, INT, FLOAT, BOOL, STR = BaseType.VOID, BaseType.INT, BaseType.FLOAT, BaseType.BOOL, BaseType.STR


class TypeDesc:
    """ Класс для описания типа данных.
        Сейчас поддерживаются только примитивные типы данных и функции.
        Для поддержки сложных типов (массивы и т.п.) должен быть расширен.
    """

    VOID: 'TypeDesc'
    INT: 'TypeDesc'
    FLOAT: 'TypeDesc'
    BOOL: 'TypeDesc'
    STR: 'TypeDesc'

    def __init__(self, base_type_: BaseType = None,
                 return_type: 'TypeDesc' = None, params: Sequence['TypeDesc'] = None) -> None:
        self.base_type = base_type_
        self.return_type = return_type
        self.params = params

    @property
    def func(self) -> bool:
        return self.return_type is not None

    @property
    def is_simple(self) -> bool:
        return not self.func

    def __eq__(self, other: 'TypeDesc'):
        if self.func != other.func:
            return False
        if not self.func:
            return self.base_type == other.base_type
        else:
            if self.return_type != other.return_type:
                return False
            if len(self.params) != len(other.params):
                return False
            for i in range(len(self.params)):
                if self.params[i] != other.params[i]:
                    return False
            return True

    @staticmethod
    def from_base_type(base_type_: BaseType) -> 'TypeDesc':
        return getattr(TypeDesc, base_type_.name)

    @staticmethod
    def from_str(str_decl: str) -> 'TypeDesc':
        try:
            base_type_ = BaseType(str_decl)
            return TypeDesc.from_base_type(base_type_)
        except:
            raise SemanticException(f'Неизвестный тип {str_decl}')

    def __str__(self) -> str:
        if not self.func:
            return str(self.base_type)
        else:
            res = str(self.return_type)
            res += ' ('
            for param in self.params:
                if res[-1] != '(':
                    res += ', '
                res += str(param)
            res += ')'
        return res


for base_type in BaseType:
    setattr(TypeDesc, base_type.name, TypeDesc(base_type))


class ScopeType(Enum):
    """ Перечисление для "области" декларации переменных """

    GLOBAL = 'global'
    GLOBAL_LOCAL = 'global.local'  # переменные относятся к глобальной области, но описаны в скобках (теряем имена)
    PARAM = 'param'
    LOCAL = 'local'

    def __str__(self):
        return self.value


class IdentDesc:
    """ Класс для описания переменных """

    def __init__(self, name: str, type_: TypeDesc, scope: ScopeType = ScopeType.GLOBAL, index: int = 0) -> None:
        self.name = name
        self.type = type_
        self.scope = scope
        self.index = index
        self.built_in = False

    def __str__(self) -> str:
        result = f'{self.type}, {self.scope}'
        if self.built_in:
            result += ', built-in'
        elif not self.type.func:
            result += f', {self.index}'
        return result


class IdentScope:
    """ Класс для представлений областей видимости переменных во время семантического анализа """

    def __init__(self, parent: 'IdentScope' = None) -> None:
        self.idents: dict[str, IdentDesc] = {}
        self.func: IdentDesc | None = None
        self.parent = parent
        self.var_index = 0
        self.param_index = 0

    @property
    def is_global(self) -> bool:
        return self.parent is None

    @property
    def curr_global(self) -> 'IdentScope':
        curr = self
        while curr.parent:
            curr = curr.parent
        return curr

    @property
    def curr_func(self) -> 'IdentScope':
        curr = self
        while curr and not curr.func:
            curr = curr.parent
        return curr

    def add_ident(self, ident: IdentDesc) -> IdentDesc:
        func_scope = self.curr_func
        global_scope = self.curr_global

        if ident.scope != ScopeType.PARAM:
            ident.scope = ScopeType.LOCAL if func_scope else \
                ScopeType.GLOBAL if self == global_scope else ScopeType.GLOBAL_LOCAL

        old_ident = self.get_ident(ident.name)
        if old_ident:
            error = False
            if ident.scope == ScopeType.PARAM:
                if old_ident.scope == ScopeType.PARAM:
                    error = True
            elif ident.scope == ScopeType.LOCAL:
                if old_ident.scope not in (ScopeType.GLOBAL, ScopeType.GLOBAL_LOCAL):
                    error = True
            else:
                error = True
            if error:
                raise SemanticException(f'Идентификатор {ident.name} уже объявлен')

        if not ident.type.func:
            if ident.scope == ScopeType.PARAM:
                ident.index = func_scope.param_index
                func_scope.param_index += 1
            else:
                ident_scope = func_scope if func_scope else global_scope
                ident.index = ident_scope.var_index
                ident_scope.var_index += 1

        self.idents[str(ident.name)] = ident
        return ident

    def get_ident(self, name: str) -> IdentDesc:
        scope = self
        ident = None
        while scope:
            ident = scope.idents.get(name)
            if ident:
                break
            scope = scope.parent
        return ident


""" Приводимость типов данных """
TYPE_CONVERTIBILITY = {
    INT: (FLOAT, BOOL, STR),
    FLOAT: (STR,),
    BOOL: (STR,)
}

def can_type_convert_to(from_type: TypeDesc, to_type: TypeDesc) -> bool:
    if not from_type.is_simple or not to_type.is_simple:
        return False
    return from_type.base_type in TYPE_CONVERTIBILITY and to_type.base_type in TYPE_CONVERTIBILITY[from_type.base_type]


""" Применимость к типам данных унарных операторов и тип результата """
UN_OP_TYPE_COMPATIBILITY = {
    UnOp.NOT: {
        BOOL: BOOL
    },
    UnOp.PLUS: {
        INT: INT,
        FLOAT: FLOAT
    },
    UnOp.MINUS: {
        INT: INT,
        FLOAT: FLOAT
    }
}

""" Применимость к типам данных бинарных операторов и тип результата """
BIN_OP_TYPE_COMPATIBILITY = {
    BinOp.ADD: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT,
        (STR, STR): STR
    },
    BinOp.SUB: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.MUL: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.DIV: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },
    BinOp.MOD: {
        (INT, INT): INT,
        (FLOAT, FLOAT): FLOAT
    },

    BinOp.GT: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
    },
    BinOp.LT: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
    },
    BinOp.GE: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
    },
    BinOp.LE: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
    },
    BinOp.EQ: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
        (BOOL, BOOL): BOOL,
    },
    BinOp.NE: {
        (INT, INT): BOOL,
        (FLOAT, FLOAT): BOOL,
        (STR, STR): BOOL,
        (BOOL, BOOL): BOOL,
    },

    BinOp.BIT_AND: {
        (INT, INT): INT,
    },
    BinOp.BIT_OR: {
        (INT, INT): INT,
    },

    BinOp.LOGIC_AND: {
        (BOOL, BOOL): BOOL,
    },
    BinOp.LOGIC_OR: {
        (BOOL, BOOL): BOOL,
    },
}


def semantic_error(node: AstNode, message: str):
    raise SemanticException(message, node.row, node.col)


def type_convert(expr: ExprNode, type_: TypeDesc, except_node: AstNode = None,
                 comment: str = None) -> ExprNode | None:
    """ Метод преобразования ExprNode узла AST-дерева к другому типу
        :param expr: узел AST-дерева
        :param type_: требуемый тип
        :param except_node: узел, о которого будет исключение
        :param comment: комментарий
        :return: узел AST-дерева с операцией преобразования
    """

    if expr.node_type is None:
        semantic_error(except_node, 'Тип выражения не определен')
    if expr.node_type == type_:
        return expr
    if can_type_convert_to(expr.node_type, type_):
        return TypeConvertNode(expr, type_)
    else:
        semantic_error(except_node if except_node else expr,
                       f'Тип {expr.node_type}{f' ({comment})' if comment else ''} не конвертируется в {type_}')


class SemanticChecker:
    """ Класс для проверки семантики.
        Сейчас поддерживаются только примитивные типы данных и функции.
        Для поддержки сложных типов (массивы и т.п.) должен быть доработан.
    """

    @visitor.on('AstNode')
    def semantic_check(self, AstNode, scope: IdentScope):  # noqa
        """ Нужен для работы модуля visitor (инициализации диспетчера) """
        pass

    @visitor.when(LiteralNode)
    def semantic_check(self, node: LiteralNode, scope: IdentScope):
        if isinstance(node.value, bool):
            node.node_type = TypeDesc.BOOL
        # Проверка должна быть позже bool, так как bool наследник от int
        elif isinstance(node.value, int):
            node.node_type = TypeDesc.INT
        elif isinstance(node.value, float):
            node.node_type = TypeDesc.FLOAT
        elif isinstance(node.value, str):
            node.node_type = TypeDesc.STR
        else:
            semantic_error(node, f'Неизвестный тип {type(node.value)} для {node.value}')

    @visitor.when(IdentNode)
    def semantic_check(self, node: IdentNode, scope: IdentScope):
        ident = scope.get_ident(node.name)
        if ident is None:
            semantic_error(node, f'Идентификатор {node.name} не найден')
        node.node_type = ident.type
        node.node_ident = ident

    @visitor.when(TypeNode)
    def semantic_check(self, node: TypeNode, scope: IdentScope):
        try:
            node.type = TypeDesc.from_str(node.desc)
        except SemanticException as e:
            semantic_error(node, e.message)

    @visitor.when(IncDecNode)
    def semantic_check(self, node: IncDecNode, scope: IdentScope):
        node.var.semantic_check(self, scope)
        if not node.var.node_type.is_simple or node.var.node_type.base_type != INT or not node.var.node_ident:
            semantic_error(node, f'Оператор {node.op} можно применить только к переменным целого типа')
        node.node_type = node.var.node_type

    @visitor.when(UnOpNode)
    def semantic_check(self, node: UnOpNode, scope: IdentScope):
        node.arg.semantic_check(self, scope)

        if node.arg.node_type.is_simple:
            compatibility = UN_OP_TYPE_COMPATIBILITY[node.op]
            arg_type = node.arg.node_type.base_type
            if arg_type in compatibility:
                node.node_type = TypeDesc.from_base_type(compatibility[arg_type])
                return

            if node.arg.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg_type in TYPE_CONVERTIBILITY[node.arg.node_type.base_type]:
                    if arg_type in compatibility:
                        node.arg = type_convert(node.arg, TypeDesc.from_base_type(arg_type))
                        node.node_type = TypeDesc.from_base_type(compatibility[arg_type])
                        return

        semantic_error(node,f'Оператор {node.op} не применим к типу {node.arg.node_type}')

    @visitor.when(BinOpNode)
    def semantic_check(self, node: BinOpNode, scope: IdentScope):
        node.arg1.semantic_check(self, scope)
        node.arg2.semantic_check(self, scope)

        if node.arg1.node_type.is_simple or node.arg2.node_type.is_simple:
            compatibility = BIN_OP_TYPE_COMPATIBILITY[node.op]
            args_types = (node.arg1.node_type.base_type, node.arg2.node_type.base_type)
            if args_types in compatibility:
                node.node_type = TypeDesc.from_base_type(compatibility[args_types])  # noqa
                return

            if node.arg2.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg2_type in TYPE_CONVERTIBILITY[node.arg2.node_type.base_type]:
                    args_types = (node.arg1.node_type.base_type, arg2_type)
                    if args_types in compatibility:
                        node.arg2 = type_convert(node.arg2, TypeDesc.from_base_type(arg2_type))
                        node.node_type = TypeDesc.from_base_type(compatibility[args_types])  # noqa
                        return
            if node.arg1.node_type.base_type in TYPE_CONVERTIBILITY:
                for arg1_type in TYPE_CONVERTIBILITY[node.arg1.node_type.base_type]:
                    args_types = (arg1_type, node.arg2.node_type.base_type)
                    if args_types in compatibility:
                        node.arg1 = type_convert(node.arg1, TypeDesc.from_base_type(arg1_type))
                        node.node_type = TypeDesc.from_base_type(compatibility[args_types])  # noqa
                        return

        semantic_error(node, f'Оператор {node.op} не применим к типам ({node.arg1.node_type}, {node.arg2.node_type})')

    @visitor.when(CallNode)
    def semantic_check(self, node: CallNode, scope: IdentScope):
        func = scope.get_ident(node.name.name)
        if func is None:
            semantic_error(node, f'Функция {node.name.name} не найдена')
        if not func.type.func:
            semantic_error(node, f'Идентификатор {func.name} не является функцией')
        if len(func.type.params) != len(node.params):
            semantic_error(node, f'Кол-во аргументов {func.name} не совпадает (ожидалось {len(func.type.params)}, передано {len(node.params)})')
        params = []
        error = False
        decl_params_str = fact_params_str = ''
        for i in range(len(node.params)):
            param: ExprNode = node.params[i]
            param.semantic_check(self, scope)
            if len(decl_params_str) > 0:
                decl_params_str += ', '
            decl_params_str += str(func.type.params[i])
            if len(fact_params_str) > 0:
                fact_params_str += ', '
            fact_params_str += str(param.node_type)
            try:
                params.append(type_convert(param, func.type.params[i]))
            except:
                type_convert(param, func.type.params[i])
                error = True
        if error:
            semantic_error(node, f'Фактические типы ({fact_params_str}) аргументов функции {func.name} не совпадают с формальными ({decl_params_str}) и не приводимы')
        else:
            node.params = tuple(params)
            node.name.node_type = func.type
            node.name.node_ident = func
            node.node_type = func.type.return_type

    @visitor.when(AssignNode)
    def semantic_check(self, node: AssignNode, scope: IdentScope):
        node.var.semantic_check(self, scope)
        node.value.semantic_check(self, scope)
        node.value = type_convert(node.value, node.var.node_type, node.value, 'присваиваемое значение')
        node.node_type = node.var.node_type

    @visitor.when(VarsDeclNode)
    def semantic_check(self, node: VarsDeclNode, scope: IdentScope):
        node.type.semantic_check(self, scope)
        for var in node.vars:
            var_node: IdentNode = var.var if isinstance(var, AssignNode) else var  # noqa
            try:
                scope.add_ident(IdentDesc(var_node.name, node.type.type))
            except SemanticException as e:
                semantic_error(var_node, e.message)
            var.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(ReturnNode)
    def semantic_check(self, node: ReturnNode, scope: IdentScope):
        node.value.semantic_check(self, IdentScope(scope))
        func = scope.curr_func
        if func is None:
            semantic_error(node, 'Оператор return может использоваться только внутри функции')
        node.value = type_convert(node.value, func.func.type.return_type, node.value, 'возвращаемое значение')
        node.node_type = TypeDesc.VOID

    @visitor.when(IfNode)
    def semantic_check(self, node: IfNode, scope: IdentScope):
        node.cond.semantic_check(self, scope)
        node.cond = type_convert(node.cond, TypeDesc.BOOL, None, 'условие')
        node.then_stmt.semantic_check(self, IdentScope(scope))
        if node.else_stmt:
            node.else_stmt.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(WhileNode)
    def semantic_check(self, node: WhileNode, scope: IdentScope):
        node.cond.semantic_check(self, scope)
        node.cond = type_convert(node.cond, TypeDesc.BOOL, None, 'условие')
        node.body.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(ForNode)
    def semantic_check(self, node: ForNode, scope: IdentScope):
        scope = IdentScope(scope)
        node.init.semantic_check(self, scope)
        node.cond.semantic_check(self, scope)
        node.cond = type_convert(node.cond, TypeDesc.BOOL, None, 'условие')
        node.next.semantic_check(self, scope)
        node.body.semantic_check(self, IdentScope(scope))
        node.node_type = TypeDesc.VOID

    @visitor.when(FuncNode)
    def semantic_check(self, node: FuncNode, scope: IdentScope):
        if scope.curr_func:
            semantic_error(node, f'Объявление функции ({node.name.name}) внутри другой функции не поддерживается')
        parent_scope = scope
        node.type.semantic_check(self, scope)
        scope = IdentScope(scope)

        # временно хоть какое-то значение, чтобы при добавлении параметров находить scope функции
        scope.func = True  # noqa
        params: list[TypeDesc] = []
        for param in node.params:
            param.type.semantic_check(self, scope)
            ident: IdentNode = param.vars[0]  # noqa
            ident.node_type = param.type.type
            try:
                node.name.node_ident = scope.add_ident(IdentDesc(ident.name, ident.node_type, ScopeType.PARAM))
            except SemanticException:
                semantic_error(ident, f'Параметр {ident.name} уже объявлен')
            node.node_type = TypeDesc.VOID
            param.node_ident = scope.get_ident(ident.name)
            params.append(param.type.type)

        type_ = TypeDesc(None, node.type.type, tuple(params))
        func_ident = IdentDesc(node.name.name, type_)
        scope.func = func_ident
        node.name.node_type = type_
        try:
            node.name.node_ident = parent_scope.curr_global.add_ident(func_ident)
        except SemanticException as e:
            semantic_error(node.name, f'Повторное объявление функции {node.name.name}')
        node.body.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID

    @visitor.when(StmtListNode)
    def semantic_check(self, node: StmtListNode, scope: IdentScope):
        if not node.program:
            scope = IdentScope(scope)
        for stmt in node.stmts:
            stmt.semantic_check(self, scope)
        node.node_type = TypeDesc.VOID


BUILT_IN_OBJECTS = '''
    string read() { }
    void print(string p0) { }
    void println(string p0) { }
    int to_int(string p0) { }
    float to_float(string p0) { }
'''


def prepare_global_scope() -> IdentScope:
    from .parser import parse

    prog = parse(BUILT_IN_OBJECTS)
    checker = SemanticChecker()
    scope = IdentScope()
    checker.semantic_check(prog, scope)
    for name, ident in scope.idents.items():
        ident.built_in = True
    scope.var_index = 0
    return scope


def semantic_check(program: AstNode) -> None:
    checker = SemanticChecker()
    scope = prepare_global_scope()
    checker.semantic_check(program, scope)
