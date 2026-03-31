from pathlib import Path
from typing import TypeVar

from lark import Lark, Transformer, v_args, GrammarError, UnexpectedCharacters

from .ast import *
from .errors import ParserException

grammar_path = Path(__file__).parent / 'parser.lark'
grammar = grammar_path.read_text()


T = TypeVar('T')

@v_args(meta=True)
class ASTBuilder(Transformer):

    def _process_meta(self, node: T, meta) -> T:
        # line и column могут быть не заданы (для пустых альтернатив, видимо)
        node.row = getattr(meta, 'line') if hasattr(meta, 'line') else None
        node.col = getattr(meta, 'column') if hasattr(meta, 'column') else None
        return node

    # вначале идут методы, которые соответствуют именам синтаксических правил в грамматике

    def type(self, meta, children) -> TypeNode:
        result = TypeNode(str(children[0]))
        return self._process_meta(result, meta)

    def block(self, meta, children) -> StmtListNode:
        child = children[0]
        return StmtListNode(child) if not isinstance(child, StmtListNode) else child

    def func(self, meta, children) -> FuncNode:
        result = FuncNode(children[0], children[1], list(children[2:-1]), children[-1])
        return self._process_meta(result, meta)

    def empty_expr(self, meta, children) -> LiteralNode:
        return LiteralNode('true')

    # вызывается, если не найдем метод, соответствующий имени правила (data)
    def __default__(self, data, children, meta) -> AstNode | str:
        if isinstance(data, str) and data.upper() == data:
            return data

        result = None

        if data in ('prefix_dec', 'prefix_inc', 'suffix_dec', 'suffix_inc'):
            op = IncDecOp[data.upper()]
            result = IncDecNode(op, *children)

        if data in ('plus', 'minus', 'not'):
            op = UnOp[data.upper()]
            result = UnOpNode(op, *children)

        if data in ('mul', 'div', 'mod',
                    'add', 'sub',
                    'gt', 'ge', 'lt', 'le',
                    'eq', 'ne',
                    'logic_and',
                    'logic_or'):
            op = BinOp[data.upper()]
            result = BinOpNode(op, *children)

        if not result:
            try:
                cls = eval(''.join(x.capitalize() or '_' for x in data.split('_')) + 'Node')
                result = cls(*children)
            except Exception as e:
                # только для удобства отладки (для точки остановки на raise)
                raise e

        return self._process_meta(result, meta)


def parse(program: str) -> StmtListNode:
    try:
        parser = Lark(grammar, start="start", propagate_positions=True)
        parse_tree = parser.parse(str(program))
    except UnexpectedCharacters as e:
        allow = (t.pattern.value or t.pattern.raw if t.pattern.type == 'str' else a
                 for a in e.allowed for t in parser.terminals if t.name == a)
        error_msg = f'Ожидалось {', '.join(allow)}'
        if hasattr(e, '_context'):
            error_msg += f', получено:\n{e._context}\n'
        raise ParserException(error_msg, row=e.line, col=e.column)

    ast_tree: StmtListNode = ASTBuilder().transform(parse_tree)
    ast_tree.program = True
    return ast_tree
