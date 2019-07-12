from .parser import JavaParser, JavaSyntaxError, parse_file, parse_str
from .tokenize import tokenize

import unittest

class UnitTests(unittest.TestCase):
    def test_parser(self):
        import os.path
        import pprint
        from textwrap import indent
        self.maxDiff = 1000
        with open(os.path.join(os.path.dirname(__file__), 'test.java'), 'rb') as file:
            self.assertIsNotNone(parse_file(file, parser=JavaParser), 'parse_file returned None')        

def main(args=None):
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Parse a javapy file')
    parser.add_argument('file', metavar='FILE', type=argparse.FileType('rb'),
                        help='The java file to parse')
    parser.add_argument('--type', choices=['Java'],
                        help='What syntax to use')
    parser.add_argument('--out', metavar='FILE', type=Path,
                        help='Where to save the output. Special name "STDOUT" can be used to output to the console. Special name "NUL" can be used to not output anything at all.')

    args = parser.parse_args(args)

    if args.type == 'Java':
        parser = JavaParser
    else:
        assert False, f"args.type == {parser!r}"

    with args.file as file:
        unit = parse_file(file, parser)

    if hasattr(args, 'out'):
        if str(args.out) == 'STDOUT':
            filename = args.file.name
            print(unit)
        elif str(args.out) != 'NUL':
            with args.out.open('w') as file:
                file.write(str(unit))
                filename = file.name

    else:
        import os.path

        filename = os.path.join(os.path.dirname(args.file.name), os.path.splitext(args.file.name)[0] + '.java')

        with open(filename, 'w') as file:
            file.write(str(unit))

    print("Converted", filename)

if __name__ == "__main__":
    main()