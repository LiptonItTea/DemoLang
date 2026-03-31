import argparse
import sys
import traceback  # noqa

from .parser import parse, ParserException
from .ast_printer import AstPrinter
from .semantic import semantic_check, SemanticException


def execute(program: str, msil_only: bool = False, jbc_only: bool = False, file_name: str = None) -> None:
    try:
        program = parse(program)
    except ParserException as e:
        # traceback.print_exc(file=sys.stderr)
        print(f'Ошибка:\n{e.message}', file=sys.stderr)
        exit(1)

    if not (msil_only or jbc_only):
        print('ast:')
        AstPrinter.print(program)

    try:
        semantic_check(program)
    except SemanticException as e:
        # traceback.print_exc(file=sys.stderr)
        print(f'Ошибка: {e.message}', file=sys.stderr)
        exit(2)

    if not (msil_only or jbc_only):
        print()
        print('semantic-check:')
        AstPrinter.print(program)


def main() -> None:
    parser = argparse.ArgumentParser(description='Compiler demo program (msil)')
    parser.add_argument('src', type=str, help='source code file')
    parser.add_argument('--msil-only', default=False, action='store_true', help='print only msil code (no ast)')
    parser.add_argument('--jbc-only', default=False, action='store_true', help='print only java byte code (no ast)')
    args = parser.parse_args()

    with open(args.src, mode='r', encoding='utf-8') as f:
        src = f.read()

    execute(src, args.msil_only, args.jbc_only, file_name=args.src)
