from typing import Any


class CompilerException(Exception):
    """ Базовый класс исключений """

    def __init__(self, message, row: int = None, col: int = None, **kwargs: Any) -> None:
        if row or col:
            message += ' ('
            if row:
                message += f'строка: {row}'
                if col:
                    message += ', '
            if col:
                message += f'позиция: {col}'
            message += ')'
        self.message = message


class ParserException(CompilerException):
    pass


class SemanticException(CompilerException):
    pass
