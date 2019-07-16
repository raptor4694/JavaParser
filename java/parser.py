import io
import java.tree as tree
from java.util import *
from java.tokenize import *
from typeguard import check_type, check_argument_types
from typing import Union, List, Optional, Type, Tuple

class JavaParser:
    def __init__(self, tokens, filename='<unknown source>'):
        check_type('filename', filename, str)
        self.tokens = LookAheadListIterator(filter(lambda token: token.type not in (NEWLINE, INDENT, DEDENT), tokens))
        self._scope = [False]
        self.filename = filename
        self._pre_stmts: list = None
        assert self.token.type == ENCODING
        self.next() # skip past the encoding token

        class PreStmtManager:
            def __init__(self):
                self.stack = []

            def get_stmts(self) -> List[tree.Statement]:
                if self.stack:
                    return self.stack[-1]
                else:
                    return None

            def append(self, stmt: tree.Statement):
                self.get_stmts().append(stmt)

            def apply(self, stmt: tree.Statement):
                stmts = self.get_stmts()
                if len(stmts) == 0:
                    return stmt
                elif isinstance(stmt, tree.Block):
                    add = 0
                    for stmt2 in stmts:
                        stmt.stmts.insert(add, stmt2)
                        add += 1
                    return stmt
                else:
                    return tree.Block([*stmts, stmt])

            def __bool__(self):
                return bool(self.get_stmts())

            def __iter__(self):
                return iter(self.get_stmts())

            def __enter__(self):
                self.stack.append([])

            def __exit__(self, exc_typ, exc_val, exc_tb):
                self.stack.pop()

        self.pre_stmts = PreStmtManager()

    @property
    def token(self) -> TokenInfo:
        return self.tokens.look()

    def next(self):
        next(self.tokens)
        while self.token.type == COMMENT:
            next(self.tokens)

    @property
    def doc(self):
        last = self.tokens.look(-1)
        if last.type == COMMENT and last.string != '/**/' and last.string[0:3] == '/**':
            return last.string

    def tok_match(self, token, test):
        if isinstance(test, (tuple, set)):
            for subtest in test:
                if self.tok_match(token, subtest):
                    return True
            return False
        elif isinstance(test, str):
            return token.string == test
        elif isinstance(test, int):
            return token.exact_type == test #or test == NEWLINE and token.string == ';' # or test in (NEWLINE, DEDENT) and token.type == ENDMARKER
        else:
            check_type('test', test, Union[str, tuple])

    def accept(self, *tests):
        self.tokens.push_marker()
        last = None
        for test in tests:
            if not self.tok_match(self.token, test):
                # if self.token.type == DEDENT and (test == NEWLINE or isinstance(test, (set, tuple)) and NEWLINE in test):
                #     continue
                self.tokens.pop_marker(reset=True)
                return None
            last = self.token.string
            self.next()
    
        if last == '': last = True
        self.tokens.pop_marker(reset=False)
        return last

    def would_accept(self, *tests):
        look = 0
        for test in tests:
            token = self.tokens.look(look)
            
            # while token.type == COMMENT \
            #         or scope > 0 and token.type in (INDENT, DEDENT, NEWLINE):
            #     look += 1
            #     token = self.tokens.look(look)
            # if token.string in '([{':
            #     scope += 1
            # elif token.string in ')]}':
            #     scope -= 1

            if not self.tok_match(token, test):
                # if self.token.type == DEDENT and (test == NEWLINE or isinstance(test, (set, tuple)) and NEWLINE in test):
                #     continue
                return False

            look += 1

        return True

    def test_str(self, test):
        if isinstance(test, (tuple, set)):
            return join_natural((self.test_str(x) for x in test), word='or')
        elif isinstance(test, int):
            return tok_name[test]
        elif isinstance(test, str):
            return repr(test)
        else:
            raise TypeError(f'invalid test: {test!r}')

    def require(self, *tests):
        result = self.accept(*tests)
        if not result:
            raise JavaSyntaxError(f'expected {" ".join(self.test_str(x) for x in tests)}', got=self.token, at=self.position())
        return result
    
    def position(self):
        """ Returns a tuple of (filename, line#, column#, line) """
        return (self.filename, *self.token.start, self.token.line)

    def parse_ident(self):
        return self.require(NAME)

    def parse_name(self):
        return tree.Name(self.parse_ident())

    def parse_class_name(self):
        token = self.token
        name = self.parse_name()
        if name == 'var':
            raise JavaSyntaxError("'var' cannot be used as a type name", at=self.position(), token=token)
        return name

    def parse_qual_name(self):
        result = self.parse_ident()
        while self.would_accept('.', NAME):
            self.next()
            result += '.' + self.parse_ident()
        return tree.Name(result)

    #region Compilation Unit
    def parse_compilation_unit(self):
        doc = self.doc
        modifiers, annotations = self.parse_mods_and_annotations(newlines=True)
        
        if not modifiers and self.would_accept('package'):
            package = self.parse_package_declaration(doc, annotations)
            doc = self.doc
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)
        else:
            package = None

        if not modifiers and not annotations:
            doc = None
            imports = self.parse_import_section()
        else:
            if self.would_accept(('from', 'import')):
                raise JavaSyntaxError("expected 'class', 'interface', '@interface', or 'enum' here", got=self.token, at=self.position())
            imports = self.parse_import_section()

        # re-parse modifiers and annotations if the were used up
        if not modifiers and not annotations:
            doc = self.doc
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        if not modifiers and not annotations:
            while self.accept(';'):
                pass

        if package is None and not modifiers and self.would_accept(('open', 'module')):
            return self.parse_module_declaration(imports, annotations, doc)

        if self.token.type != ENDMARKER or modifiers or annotations:
            types = self.parse_type_declarations(doc, modifiers, annotations, imports)
        else:
            types = []

        if self.token.type != ENDMARKER:
            raise JavaSyntaxError(f"unexpected token {simple_token_str(self.token)}", at=self.position())

        return tree.CompilationUnit(package=package, imports=imports, types=types)

    def parse_module_declaration(self, imports, annotations, doc):
        isopen = bool(self.accept('open'))
        self.require('module')
        name = self.parse_qual_name()
        self.require('{')
        members = []
        while not self.would_accept('}'):
            members.append(self.parse_directive())
        self.require('}')
        return tree.ModuleCompilationUnit(name=name, open=isopen, imports=imports, annotations=annotations, doc=doc, members=members)
    
    #endregion Compilation Unit

    #region Declarations
    def parse_package_declaration(self, doc=None, annotations=None):
        if doc is None and self.token.type == STRING:
            doc = self.token.string
            self.next()
        if annotations is None:
            annotations = self.parse_annotations(newlines=True)
        
        self.require('package')
        name = self.parse_qual_name()
        self.require(';')

        return tree.Package(name=name, doc=doc, annotations=annotations)

    def parse_import_section(self) -> List[tree.Import]:
        imports = []
        while self.would_accept('import'):
            imports.extend(self.parse_import_declarations())    
        return imports

    def parse_import_declarations(self) -> List[tree.Import]:
        self.require('import')
        static = bool(self.accept('static'))
        name, wildcard = self.parse_import_name()
        self.require(';')
        return [tree.Import(name=name, static=static, wildcard=wildcard)]

    def parse_import_name(self):
        name = self.parse_qual_name()
        wildcard = bool(self.accept('.', '*'))
        return name, wildcard

    def parse_directive(self):
        doc = self.doc
        if self.would_accept('requires'):
            return self.parse_requires_directive(doc)
        elif self.would_accept('exports'):
            return self.parse_exports_directive(doc)
        elif self.would_accept('opens'):
            return self.parse_opens_directive(doc)
        elif self.would_accept('uses'):
            return self.parse_uses_directive(doc)
        elif self.would_accept('provides'):
            return self.parse_provides_directive(doc)
        else:
            raise JavaSyntaxError("expected 'requires', 'exports', 'opens', 'uses', or 'provides'", got=self.token, at=self.position())

    def parse_requires_directive(self, doc):
        self.require('requires')
        modifiers = []
        while self.would_accept(('transitive', 'static')):
            modifiers.append(tree.Modifier(self.token.string))
            self.next()
        name = self.parse_qual_name()
        self.require(';')
        return tree.RequiresDirective(name=name, modifiers=modifiers, doc=doc)

    def parse_exports_directive(self, doc):
        self.require('exports')
        name = self.parse_qual_name()
        to = []
        if self.accept('to'):
            to.append(self.parse_qual_name())
            while self.accept(','):
                to.append(self.parse_qual_name())
        self.require(';')
        return tree.ExportsDirective(name=name, to=to, doc=doc)

    def parse_opens_directive(self, doc):
        self.require('opens')
        name = self.parse_qual_name()
        to = []
        if self.accept('to'):
            to.append(self.parse_qual_name())
            while self.accept(','):
                to.append(self.parse_qual_name())
        self.require(';')
        return tree.OpensDirective(name=name, to=to, doc=doc)

    def parse_uses_directive(self, doc):
        self.require('uses')
        name = self.parse_qual_name()
        if str(name) == 'var' or str(name).endswith('.var'):
            last = self.tokens.last()
            raise JavaSyntaxError("'var' cannot be used as a type name", at=(self.filename, *last.start, last.line))
        self.require(';')
        return tree.UsesDirective(name=name, doc=doc)

    def parse_provides_directive(self, doc):
        self.require('provides')
        name = self.parse_qual_name()
        if str(name) == 'var' or str(name).endswith('.var'):
            last = self.tokens.last()
            raise JavaSyntaxError("'var' cannot be used as a type name", at=(self.filename, *last.start, last.line))
        provides = []
        if self.accept('with'):
            provides.append(self.parse_qual_name())
            while self.accept(','):
                provides.append(self.parse_qual_name())
        self.require(';')
        return tree.ProvidesDirective(name=name, provides=provides, doc=doc)

    def parse_type_declarations(self, doc=None, modifiers=None, annotations=None, imports: List[tree.Import]=None) -> List[tree.TypeDeclaration]:
        types = [self.parse_type_declaration(doc, modifiers, annotations)]
        while self.token.type != ENDMARKER:
            if not self.accept(';'):
                types.append(self.parse_type_declaration())
        return types

    def parse_type_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None:
            doc = self.doc
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)
        
        if self.would_accept('class'):
            return self.parse_class_declaration(doc, modifiers, annotations)
        elif self.would_accept('interface'):
            return self.parse_interface_declaration(doc, modifiers, annotations)
        elif self.would_accept('enum'):
            return self.parse_enum_declaration(doc, modifiers, annotations)
        elif self.would_accept('@', 'interface'):
            return self.parse_annotation_declaration(doc, modifiers, annotations)
        else:
            raise JavaSyntaxError(f"expected 'class', 'interface', 'enum', or '@interface' here", got=self.token, at=self.position())
        
    def parse_mods_and_annotations(self, newlines=True):
        modifiers = []
        annotations = []
        while True:
            if self.would_accept('@') and not self.would_accept('@', 'interface'):
                annotations.append(self.parse_annotation())
            elif self.would_accept(tree.Modifier.VALUES):
                modifiers.append(tree.Modifier(self.token.string))
                self.next()
            else:
                return modifiers, annotations
   
    def parse_class_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None:
            doc = self.doc
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        self.require('class')

        name = self.parse_class_name()
        typeparams = self.parse_type_parameters_opt() or []
        superclass = self.accept('extends') and self.parse_generic_type()
        interfaces = self.parse_generic_type_list() if self.accept('implements') else []

        members = self.parse_class_body(self.parse_class_member)

        return tree.ClassDeclaration(name=name, typeparams=typeparams, superclass=superclass, interfaces=interfaces, members=members, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_interface_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None and self.token.type == STRING:
            doc = self.token.string
            self.next()
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        self.require('interface')

        name = self.parse_class_name()
        typeparams = self.parse_type_parameters_opt() or []
        interfaces = self.parse_generic_type_list() if self.accept('extends') else []

        members = self.parse_class_body(self.parse_interface_member)

        return tree.InterfaceDeclaration(name=name, typeparams=typeparams, interfaces=interfaces, members=members, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_enum_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None and self.token.type == STRING:
            doc = self.token.string
            self.next()
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        self.require('enum')

        name = self.parse_class_name()
        interfaces = self.parse_generic_type_list() if self.accept('implements') else []

        fields, members = self.parse_enum_body()

        return tree.EnumDeclaration(name=name, interfaces=interfaces, fields=fields, members=members, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_annotation_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None and self.token.type == STRING:
            doc = self.token.string
            self.next()
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        self.require('@', 'interface')

        name = self.parse_class_name()
        members = self.parse_class_body(self.parse_annotation_member)

        return tree.AnnotationDeclaration(name=name, members=members, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_method_or_field_declaration(self, doc=None, modifiers=None, annotations=None, interface=False):
        if doc is None:
            doc = self.doc
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        typeparams = self.parse_type_parameters_opt()

        if typeparams:
            if self.would_accept(NAME, '('):
                name=self.parse_name()
                return self.parse_constructor_rest(name=name, typeparams=typeparams, doc=doc, modifiers=modifiers, annotations=annotations)
            else:
                typ = tree.VoidType() if self.accept('void') else self.parse_type(annotations=[])
                return self.parse_method_rest(return_type=typ, name=self.parse_name(), typeparams=typeparams, doc=doc, modifiers=modifiers, annotations=annotations)
        elif self.accept('void'):
            return self.parse_method_rest(return_type=tree.VoidType(), name=self.parse_name(), doc=doc, modifiers=modifiers, annotations=annotations)
        else:
            if not interface and self.would_accept(NAME, '('):
                name = self.parse_name()
                return self.parse_constructor_rest(name=name, typeparams=typeparams, doc=doc, modifiers=modifiers, annotations=annotations)
            else:
                typ = self.parse_type(annotations=[])
                name = self.parse_name()
                if self.would_accept('('):
                    return self.parse_method_rest(return_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations)
                else:
                    return self.parse_field_rest(var_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations, require_init=interface)

    def parse_annotation_method_or_field_declaration(self, doc=None, modifiers=None, annotations=None):
        if doc is None and self.token.type == STRING:
            doc = self.token.string
            self.next()
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=True)

        if 'static' in modifiers:
            typeparams = self.parse_type_parameters_opt()
            if typeparams:
                typ = tree.VoidType() if self.accept('void') else self.parse_type(annotations=[])
                return self.parse_method_rest(return_type=typ, name=self.parse_name(), typeparams=typeparams, doc=doc, modifiers=modifiers, annotations=annotations)
            elif self.accept('void'):
                return self.parse_method_rest(return_type=tree.VoidType(), name=self.parse_name(), doc=doc, modifiers=modifiers, annotations=annotations)
            else:
                typ = self.parse_type(annotations=[])
                name = self.parse_name()
                if self.would_accept('('):
                    return self.parse_method_rest(return_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations)
                else:
                    return self.parse_field_rest(var_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations)
        
        else:
            typ = self.parse_type(annotations=[])
            name = self.parse_name()
            if self.would_accept('('):
                return self.parse_annotation_property_rest(prop_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations)
            else:
                return self.parse_field_rest(var_type=typ, name=name, doc=doc, modifiers=modifiers, annotations=annotations)
            
    def parse_method_rest(self, *, return_type, name, typeparams=None, doc=None, modifiers=[], annotations=[]):
        params = self.parse_parameters()
        if self.would_accept('[') or self.would_accept('@'):
            dimensions = self.parse_dimensions()
            if isinstance(return_type, tree.ArrayType):
                return_type.dimensions += dimensions
            else:
                return_type = tree.ArrayType(return_type, dimensions)
        throws = self.parse_generic_type_list() if self.accept('throws') else []
        if self.would_accept('{'):
            body = self.parse_function_body()
        else:
            self.require(';')
            body = None

        return tree.FunctionDeclaration(name=name, return_type=return_type, params=params, throws=throws, body=body, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_constructor_rest(self, *, name, typeparams=None, doc=None, modifiers=[], annotations=[]):
        params = self.parse_parameters()
        throws = self.parse_generic_type_list() if self.accept('throws') else []
        body = self.parse_function_body()
        return tree.ConstructorDeclaration(name=name, params=params, throws=throws, body=body, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_function_body(self):
        body = self.parse_block()
        if not isinstance(body, tree.Block):
            body = tree.Block(stmts=[body])
        return body

    def parse_annotation_property_rest(self, *, prop_type, name, doc=None, modifiers=[], annotations=[]):
        self.require('(', ')')
        dimensions = self.parse_dimensions_opt()
        default = self.accept('default') and self.parse_annotation_value()
        self.require(';')
        return tree.AnnotationProperty(type=prop_type, name=name, default=default, doc=doc, modifiers=modifiers, annotations=annotations, dimensions=dimensions)

    def parse_field_rest(self, *, var_type, name, doc=None, modifiers=[], annotations=[], require_init=False):
        declarators = [self.parse_declarator_rest(name, require_init, array=isinstance(var_type, tree.ArrayType))]
        while self.accept(','):
            declarators.append(self.parse_declarator(require_init, array=isinstance(var_type, tree.ArrayType)))
        self.require(';')
        return tree.FieldDeclaration(type=var_type, declarators=declarators, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_declarator(self, require_init=False, array=False):
        return self.parse_declarator_rest(self.parse_name(), require_init, array)

    def parse_declarator_rest(self, name, require_init=False, array=False):
        dimensions = self.parse_dimensions_opt()
        accept = self.require if require_init else self.accept
        init = accept('=') and self.parse_initializer(dimensions or array)
        return tree.VariableDeclarator(name=name, init=init, dimensions=dimensions)

    def parse_parameters(self, allow_this=True):
        self.require('(')
        if self.would_accept(')'):
            params = []
        else:
            if allow_this:
                param = self.parse_parameter_opt_this()
            else:
                param = self.parse_parameter()
            params = [param]
            if not param.variadic:
                while self.accept(','):
                    param = self.parse_parameter()
                    params.append(param)
                    if param.variadic:
                        break
        self.require(')')
        return params

    def parse_parameter_opt_this(self):
        modifiers, annotations = self.parse_mods_and_annotations(newlines=False)
        typ = self.parse_type(annotations=[])
        if not modifiers and self.accept('this'):
            return tree.ThisParameter(type=typ, annotations=annotations)
        else:
            variadic = bool(self.accept('...'))
            name = self.parse_name()
            if not variadic and not modifiers and self.accept('.', 'this'):
                return tree.ThisParameter(type=typ, annotations=annotations, qualifier=name)
            dimensions = self.parse_dimensions_opt()
            return tree.FormalParameter(type=typ, name=name, variadic=variadic, modifiers=modifiers, annotations=annotations, dimensions=dimensions)

    def parse_parameter(self):
        modifiers, annotations = self.parse_mods_and_annotations(newlines=False)
        typ = self.parse_type(annotations=[])
        variadic = bool(self.accept('...'))
        name = self.parse_name()
        dimensions = self.parse_dimensions_opt()
        return tree.FormalParameter(type=typ, name=name, variadic=variadic, modifiers=modifiers, annotations=annotations, dimensions=dimensions)

    def parse_class_body(self, parse_member):
        self.require('{')
        members = []
        while not self.would_accept(('}', ENDMARKER)):
            if not self.accept(';'):
                members.extend(parse_member())
        self.require('}')

        return members

    def parse_enum_body(self):
        self.require('{')
        fields = []
        members = []

        while not self.would_accept((';', '}', ENDMARKER)):
            fields.append(self.parse_enum_field())
            if not self.accept(','):
                break
        
        if self.accept(';'):
            while not self.would_accept(('}', ENDMARKER)):
                if not self.accept(';'):
                    members.extend(self.parse_class_member())
            
        self.require('}')

        return fields, members

    def parse_class_member(self):
        doc = self.doc
        if self.would_accept('static', '{'):
            self.next() # skip past the 'static' token
            body = self.parse_block()
            return [tree.InitializerBlock(body=body, static=True, doc=doc)]
        elif self.would_accept('{'):
            body = self.parse_block()
            return [tree.InitializerBlock(body=body, static=False, doc=doc)]
        else:
            modifiers, annotations = self.parse_mods_and_annotations()
            if self.would_accept(('class', 'interface', '@', 'enum')):
                return [self.parse_type_declaration(doc, modifiers, annotations)]
            else:
                result = self.parse_method_or_field_declaration(doc, modifiers, annotations)
                if isinstance(result, (list, tuple)):
                    return result
                else:
                    return [result]

    def parse_interface_member(self):
        doc = self.doc
        modifiers, annotations = self.parse_mods_and_annotations(newlines=True)
        if self.would_accept(('class', 'interface', '@', 'enum')):
            return [self.parse_type_declaration(doc, modifiers, annotations)]
        else:
            result = self.parse_method_or_field_declaration(doc, modifiers, annotations, interface=True)
            if isinstance(result, (list, tuple)):
                return result
            else:
                return [result]

    def parse_enum_field(self, doc=None, annotations=None):
        if doc is None:
            doc = self.doc
        if annotations is None:
            annotations = self.parse_annotations()
        name = self.parse_name()
        if self.would_accept('('):
            args = self.parse_args()
        else:
            args = None
        if self.would_accept('{'):
            members = self.parse_class_body(self.parse_class_member)
        else:
            members = None

        return tree.EnumField(name=name, args=args, members=members, doc=doc, annotations=annotations)

    def parse_annotation_member(self):
        doc = self.doc
        if self.would_accept('static', '{'):
            self.next() # skips past the 'static' token
            body = self.parse_block()
            return [tree.InitializerBlock(body=body, static=True, doc=doc)]
        elif self.would_accept('{'):
            body = self.parse_block()
            return [tree.InitializerBlock(body=body, static=False, doc=doc)]
        else:
            modifiers, annotations = self.parse_mods_and_annotations()
            if self.would_accept(('class', 'interface', '@', 'enum')):
                return [self.parse_type_declaration(doc, modifiers, annotations)]
            else:
                result = self.parse_annotation_method_or_field_declaration(doc, modifiers, annotations)
                if isinstance(result, (list, tuple)):
                    return result
                else:
                    return [result]

    #endregion Declarations

    #region Statements
    def parse_statement(self):
        with self.pre_stmts:
            if self.would_accept('{'):
                result = self.parse_block()
            elif self.would_accept('if'):
                result = self.parse_if()
            elif self.would_accept('for'):
                result = self.parse_for()
            elif self.would_accept('while'):
                result = self.parse_while()
            elif self.would_accept('do'):
                result = self.parse_do()
            elif self.would_accept('try'):
                result = self.parse_try()
            elif self.would_accept('break'):
                result = self.parse_break()
            elif self.would_accept('continue'):
                result = self.parse_continue()
            elif self.would_accept('yield'):
                result = self.parse_yield()
            elif self.would_accept('throw'):
                result = self.parse_throw()
            elif self.would_accept('result ='):
                result = self.parse_return()
            elif self.would_accept('switch'):
                result = self.parse_switch()
            elif self.would_accept('synchronized'):
                result = self.parse_synchronized()
            elif self.would_accept('assert'):
                result = self.parse_assert()
            elif self.would_accept(';'):
                result = self.parse_empty_statement()
            elif self.would_accept('else'):
                raise JavaSyntaxError("'else' without 'if'", at=self.position())
            elif self.would_accept(('case', 'default')):
                raise JavaSyntaxError(f"'{self.token.string}' outside 'switch'", at=self.position())
            else:
                result = self.parse_expr_statement()
            return self.pre_stmts.apply(result)

    def parse_empty_statement(self):
        self.require(';')
        return tree.EmptyStatement()

    def parse_expr_statement(self):
        expr = self.parse_expr()
        self.require(';')
        return tree.ExpressionStatement(expr)

    def parse_block_statement(self):
        if self.would_accept(NAME, ':', ('{', 'if', 'while', 'for', 'do', 'switch', 'synchronized', 'try')):
            label = self.parse_name()
            self.next() # skips past the ':' token
            return tree.LabeledStatement(label=label, stmt=self.parse_statement())

        if self.would_accept('final') or self.would_accept('@') and not self.would_accept('@', 'interface'):
            with self.pre_stmts:
                return self.pre_stmts.apply(self.parse_class_or_variable_decl())
        if self.would_accept(('class', 'abstract')):
            with self.pre_stmts:
                return self.pre_stmts.apply(self.parse_class_declaration())

        if self.would_accept((NAME, tree.PrimitiveType.VALUES)):
            try:
                with self.tokens, self.pre_stmts:
                    return self.pre_stmts.apply(self.parse_variable_decl())
            except JavaSyntaxError as e1:
                try:
                    with self.pre_stmts:
                        return self.pre_stmts.apply(self.parse_statement())
                except JavaSyntaxError as e2:
                    raise e2 from e1

        return self.parse_statement()

    def parse_class_or_variable_decl(self):
        doc = self.doc
        modifiers, annotations = self.parse_mods_and_annotations(newlines=True)
        if self.would_accept('class'):
            return self.parse_class_declaration(doc, modifiers, annotations)
        else:
            return self.parse_variable_decl(doc, modifiers, annotations)

    def parse_variable_decl(self, doc=None, modifiers=None, annotations=None, end=';'):
        if doc is None:
            doc = self.doc
        if modifiers is None and annotations is None:
            modifiers, annotations = self.parse_mods_and_annotations(newlines=(end == NEWLINE))
        if self.accept('var'):
            typ = tree.GenericType(name=tree.Name('var'))
        else:
            typ = self.parse_type()
        declarators = [self.parse_declarator(array=isinstance(typ, tree.ArrayType))]
        while self.accept(','):
            declarators.append(self.parse_declarator(array=isinstance(typ, tree.ArrayType)))
        self.require(end)
        return tree.VariableDeclaration(type=typ, declarators=declarators, doc=doc, modifiers=modifiers, annotations=annotations)

    def parse_block(self):
        self.require('{')
        stmts = []
        
        while not self.would_accept(('}', ENDMARKER)):
            stmts.append(self.parse_block_statement())
        self.require('}')
                
        return tree.Block(stmts)

    def parse_statement_body(self): return self.parse_statement()

    def parse_condition(self):
        self.require('(')
        expr = self.parse_expr()
        self.require(')')
        return expr

    def parse_if(self):
        self.require('if')
        condition = self.parse_condition()
        body = self.parse_statement_body()
        if self.accept('else'):
            if self.would_accept('if'):
                elsebody = self.parse_if()
            else:
                elsebody = self.parse_statement_body()
        else:
            elsebody = None
        return tree.IfStatement(condition=condition, body=body, elsebody=elsebody)

    def parse_for(self):
        self.require('for')
        control = self.parse_for_control()
        body = self.parse_statement_body()
        return tree.ForLoop(control=control, body=body)

    def parse_for_control(self):
        self.require('(')
        try:
            with self.tokens:
                return self.parse_enhanced_for_control()
        except JavaSyntaxError:
            pass

        if self.accept(';'):
            init = None
        else:
            try:
                with self.tokens:
                    init = self.parse_variable_decl(end=';')
            except JavaSyntaxError:
                init = self.parse_expr_statement()

        if self.accept(';'):
            condition = None
        else:
            condition = self.parse_expr()
            self.require(';')

        if self.would_accept(')'):
            update = []
        else:
            update = self.parse_expr_list(end=')')

        self.require(')')

        return tree.ForControl(init=init, condition=condition, update=update)

    def parse_expr_list(self, end):
        update = [self.parse_expr()]
        while self.accept(','):
            update.append(self.parse_expr())
        return update

    def parse_enhanced_for_control(self):
        var = self.parse_enhanced_for_var()
        self.require(':')
        iterable = self.parse_expr()
        self.require(')')
        return tree.EnhancedForControl(var=var, iterable=iterable)

    def parse_enhanced_for_var(self):
        modifiers, annotations = self.parse_mods_and_annotations()
        if self.accept('var'):
            typ = tree.GenericType(name=tree.Name('var'))
        else:
            typ = self.parse_type(annotations=[])
        name = self.parse_name()
        dimensions = self.parse_dimensions_opt()
        return tree.VariableDeclaration(type=typ, declarators=[tree.VariableDeclarator(name=name, dimensions=dimensions)], modifiers=modifiers, annotations=annotations)

    def parse_while(self):
        self.require('while')
        condition = self.parse_condition()
        body = self.parse_statement_body()
        return tree.WhileLoop(condition=condition, body=body)

    def parse_synchronized(self):
        self.require('synchronized')
        lock = self.parse_condition()
        body = self.parse_statement_body()
        return tree.SynchronizedBlock(lock=lock, body=body)

    def parse_do(self):
        self.require('do')
        body = self.parse_statement_body()
        self.require('while')
        condition = self.parse_condition()
        self.require(';')
        return tree.DoWhileLoop(condition=condition, body=body)

    def parse_try(self):
        self.require('try')
        if self.accept('('):
            resources = [self.parse_try_resource()]
            while self.accept(';'):
                if self.would_accept(')'):
                    break
                resources.append(self.parse_try_resource())
            self.require(')')
        else:
            resources = None
        body = self.parse_block()
        catches = []
        while self.would_accept('catch'):
            catches.append(self.parse_catch())

        finallybody = self.accept('finally') and self.parse_block()

        return tree.TryStatement(resources=resources, catches=catches, body=body, finallybody=finallybody)

    def parse_catch(self):
        self.require('catch', '(')
        
        modifiers, annotations = self.parse_mods_and_annotations(newlines=False)
        typ = self.parse_type_intersection()

        name = self.parse_name()
        catchvar = tree.CatchVar(type=typ, name=name, modifiers=modifiers, annotations=annotations)

        self.require(')')

        body = self.parse_block()

        return tree.CatchClause(var=catchvar, body=body)                

    def parse_try_resource(self):
        try:
            with self.tokens:
                modifiers, annotations = self.parse_mods_and_annotations(newlines=False)
                if self.accept('var'):
                    typ = tree.GenericType(name=tree.Name('var'))
                else:
                    typ = self.parse_generic_type()
                name = self.parse_name()
                self.require('=')
                init = self.parse_expr()
                return tree.TryResource(name=name, type=typ, init=init, modifiers=modifiers, annotations=annotations)
        except JavaSyntaxError:
            return self.parse_expr()

    def parse_switch(self):
        self.require('switch')
        condition = self.parse_condition()
        self.require('{')
        cases = []
        while not self.would_accept(('}', ENDMARKER)):
            cases.append(self.parse_case())
        self.require('}')
        return tree.Switch(condition=condition, cases=cases)

    def parse_case(self):
        if self.accept('default'):
            labels = None
        else:
            self.require('case')
            labels = self.parse_case_labels()
        if self.accept('->'):
            if self.would_accept('throw'):
                stmts = [self.parse_throw()]
            elif self.would_accept('{'):
                stmts = [self.parse_block()]
            else:
                stmts = [self.parse_expr_statement()]
            return tree.SwitchCase(labels=labels, stmts=stmts, arrow=True)
        else:
            self.require(':')
            stmts = []
            while not self.would_accept(('case', 'default', '}', ENDMARKER)):
                stmts.append(self.parse_block_statement())
            return tree.SwitchCase(labels=labels, stmts=stmts, arrow=False)

    def parse_case_labels(self):
        labels = [self.parse_case_label()]
        while self.accept(','):
            labels.append(self.parse_case_label())
        return labels

    def parse_case_label(self):
        if self.would_accept(NAME, ('->', ':')) or self.would_accept('(', NAME, ')', ('->', ':')):
            return self.parse_primary()
        else:
            return self.parse_expr()

    def parse_return(self):
        self.require('return')
        if self.accept(';'):
            return tree.ReturnStatement()
        else:
            result = tree.ReturnStatement(self.parse_expr())
            self.require(';')
            return result

    def parse_throw(self):
        self.require('throw')
        result = tree.ThrowStatement(self.parse_expr())
        self.require(';')
        return result

    def parse_break(self):
        self.require('break')
        if self.accept(';'):
            return tree.BreakStatement()
        else:
            result = tree.BreakStatement(self.parse_name())
            self.require(';')
            return result

    def parse_continue(self):
        self.require('continue')
        if self.accept(';'):
            return tree.ContinueStatement()
        else:
            result = tree.ContinueStatement(self.parse_name())
            self.require(';')
            return result

    def parse_yield(self):
        self.require('yield')
        result = tree.YieldStatement(self.parse_expr())
        self.require(';')
        return result

    def parse_assert(self):
        self.require('assert')
        condition = self.parse_expr()
        message = self.accept(':') and self.parse_expr()
        self.require(';')
        return tree.AssertStatement(condition=condition, message=message)

    #endregion Statements

    #region Type Stuff
    def parse_type_parameters_opt(self):
        if self.would_accept('<'):
            return self.parse_type_parameters()

    def parse_type_parameters(self):
        self.require('<')
        params = [self.parse_type_parameter()]
        while self.accept(','):
            params.append(self.parse_type_parameter())
        self.require('>')
        return params

    def parse_type_parameter(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        name = self.parse_name()
        bound = self.accept('extends') and self.parse_type_union()

        return tree.TypeParameter(name=name, bound=bound, annotations=annotations)

    def parse_annotations(self, newlines=True):
        annotations = []
        while self.would_accept('@') and not self.would_accept('@', 'interface'):
            annotations.append(self.parse_annotation())
        return annotations

    def parse_annotation(self):
        self.require('@')
        typ = tree.GenericType(name=self.parse_qual_name())

        if self.accept('('):
            if self.would_accept(NAME, '='):
                args = [self.parse_annotation_arg()]
                while self.accept(','):
                    args.append(self.parse_annotation_arg())
            elif not self.would_accept(')'):
                args = self.parse_annotation_value()
            self.require(')')
        else:
            args = None

        return tree.Annotation(type=typ, args=args)

    def parse_annotation_arg(self):
        name = self.parse_name()
        self.require('=')
        value = self.parse_annotation_value()
        return tree.AnnotationArgument(name, value)

    def parse_annotation_value(self):
        if self.would_accept('@'):
            return self.parse_annotation()
        elif self.would_accept('{'):
            return self.parse_annotation_array()
        else:
            return self.parse_expr()

    def parse_annotation_array(self):
        self.require('{')
        values = []
        if not self.would_accept('}'):
            if not self.accept(','):
                while True:
                    values.append(self.parse_annotation_value())
                    if not self.accept(',') or self.would_accept('}'):
                        break

        self.require('}')

        return tree.ArrayInitializer(values)

    def parse_type_args_opt(self):
        if self.would_accept('<'):
            return self.parse_type_args()

    def parse_type_args(self):
        self.require('<')
        args = []
        if not self.would_accept('>'):
            args.append(self.parse_type_arg())
            while self.accept(','):
                args.append(self.parse_type_arg())
        self.require('>')
        return args

    def parse_type_arg(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        if self.accept('?'):
            bound = self.accept(('extends', 'super'))
            base = bound and self.parse_type_union(annotations=[])
            return tree.TypeArgument(base=base, bound=bound, annotations=annotations)
        
        else:
            return self.parse_generic_type_or_array(annotations)

    def parse_type(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        typ = self.parse_base_type(annotations=[])
        if self.would_accept('[') or self.would_accept('@'):
            dimensions = self.parse_dimensions()
            typ = tree.ArrayType(typ, dimensions, annotations=annotations)
        else:
            typ.annotations += annotations
        
        return typ

    def parse_cast_type(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        typ = self.parse_base_type(annotations=[])
        if self.would_accept('[') or self.would_accept('@'):
            dimensions = self.parse_dimensions()
            typ = tree.ArrayType(typ, dimensions, annotations=annotations)
        else:
            typ.annotations += annotations

        if isinstance(typ, tree.GenericType) and self.accept('&'):
            types = [typ, self.parse_generic_type()]
            while self.accept('&'):
                types.append(self.parse_generic_type())
            typ = tree.TypeUnion(types)
        
        return typ

    def parse_base_type(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        if self.would_accept(tree.PrimitiveType.VALUES):
            name = self.token.string
            self.next()
            return tree.PrimitiveType(name, annotations=annotations)

        else:
            return self.parse_generic_type(annotations)

    def parse_generic_type(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        name = self.parse_qual_name()
        if str(name) == 'var' or str(name).endswith('.var'):
            last = self.tokens.last()
            raise JavaSyntaxError("'var' cannot be used as a type name", at=(self.filename, *last.start, last.line))
        typeargs = self.parse_type_args_opt()

        typ = tree.GenericType(name, typeargs=typeargs)

        while self.would_accept('.', NAME):
            self.next() # skips past the '.' token
            name = self.parse_name()
            if str(name) == 'var':
                last = self.tokens.last()
                raise JavaSyntaxError("'var' cannot be used as a type name", at=(self.filename, *last.start, last.line))
            typeargs = self.parse_type_args_opt()

            typ = tree.GenericType(name, typeargs=typeargs, container=typ)

        return typ

    def parse_generic_type_or_array(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        if self.would_accept(tree.PrimitiveType.VALUES):
            name = self.token.string
            next(self.token)
            dimensions = self.parse_dimensions()
            return tree.ArrayType(tree.PrimitiveType(name), dimensions, annotations=annotations)

        else:
            typ = self.parse_generic_type(annotations)
            if self.would_accept('[') or self.would_accept('@'):
                typ.annotations = []
                dimensions = self.parse_dimensions()
                typ = tree.ArrayType(typ, dimensions, annotations=annotations)
            return typ

    def parse_type_union(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        typ = self.parse_generic_type(annotations=[])

        if self.accept('&'):
            types = [typ, self.parse_generic_type()]
            while self.accept('&'):
                types.append(self.parse_generic_type())
            typ = tree.TypeUnion(types)

        else:
            typ.annotations = annotations

        return typ

    def parse_type_intersection(self, annotations=None):
        if annotations is None:
            annotations = self.parse_annotations(newlines=False)

        typ = self.parse_generic_type(annotations=[])

        if self.accept('|'):
            types = [typ, self.parse_generic_type()]
            while self.accept('|'):
                types.append(self.parse_generic_type())
            typ = tree.TypeIntersection(types)

        else:
            typ.annotations = annotations

        return typ

    def parse_generic_type_list(self):
        types = [self.parse_generic_type()]
        while self.accept(','):
            types.append(self.parse_generic_type())
        return types

    def parse_dimensions(self):
        dimensions = [self.parse_dimension()]
        while self.would_accept('[') or self.would_accept('@'):
            dimensions.append(self.parse_dimension())
        return dimensions

    def parse_dimensions_opt(self):
        if self.would_accept('[') or self.would_accept('@'):
            return self.parse_dimensions()
        else:
            return []

    def parse_dimension(self):
        if self.would_accept('@'):
            result = self.parse_annotations(newlines=False)
        else:
            result = None
        self.require('[', ']')
        return result

    #endregion Type Stuff

    #region Expressions
    def parse_expr(self):
        return self.parse_assignment()

    def parse_initializer(self, array=True):
        if array and self.would_accept('{'):
            return self.parse_array_init()
        else:
            return self.parse_expr()

    def parse_array_init(self):
        self.require('{')
        elements = []
        if not self.would_accept('}'):
            if not self.accept(','):
                elements.append(self.parse_initializer())
                while self.accept(','):
                    if self.would_accept('}'):
                        break
                    elements.append(self.parse_initializer())
        self.require('}')
        return tree.ArrayInitializer(elements)

    def parse_assignment(self):
        result = self.parse_conditional()
        if self.token.string in tree.Assignment.OPS:
            op = self.token.string
            self.next()
            result = tree.Assignment(op=op, lhs=result, rhs=self.parse_assignment())
        return result

    def parse_binary_expr(self, base_func, operators):
        result = base_func()
        while True:
            for key in operators:
                if self.accept(key):
                    result = tree.BinaryExpression(op=key, lhs=result, rhs=base_func())
                    break
            else:
                return result

    def parse_conditional(self):
        if self.would_accept(NAME, '->') or self.would_accept('('):
            try:
                with self.tokens:
                    result = self.parse_lambda()
            except JavaSyntaxError:
                result = self.parse_logic_or_expr()
        else:
            result = self.parse_logic_or_expr()            
        if self.accept('?'):
            truepart = self.parse_assignment()
            self.require(':')
            falsepart = self.parse_conditional()
            result = tree.ConditionalExpression(condition=result, truepart=truepart, falsepart=falsepart)
        return result

    def parse_logic_or_expr(self):
        result = self.parse_logic_and_expr()
        while self.accept('||'):
            result = tree.BinaryExpression(op='||', lhs=result, rhs=self.parse_logic_and_expr())
        return result

    def parse_logic_and_expr(self):
        result = self.parse_bitwise_or_expr()
        while self.accept('&&'):
            result = tree.BinaryExpression(op='&&', lhs=result, rhs=self.parse_bitwise_or_expr())
        return result

    def parse_bitwise_or_expr(self):
        result = self.parse_bitwise_xor_expr()
        while self.accept('|'):
            result = tree.BinaryExpression(op='|', lhs=result, rhs=self.parse_bitwise_xor_expr())
        return result

    def parse_bitwise_xor_expr(self):
        result = self.parse_bitwise_and_expr()
        while self.accept('^'):
            result = tree.BinaryExpression(op='^', lhs=result, rhs=self.parse_bitwise_and_expr())
        return result

    def parse_bitwise_and_expr(self):
        result = self.parse_equality()
        while self.accept('&'):
            result = tree.BinaryExpression(op='&', lhs=result, rhs=self.parse_equality())
        return result

    def parse_equality(self):
        return self.parse_binary_expr(self.parse_comp, ('==', '!='))

    def parse_comp(self):
        result = self.parse_shift()
        while True:
            if self.would_accept(('<=', '>=', '<', '>')):
                op = self.token.string
                self.next()
                result = tree.BinaryExpression(op=op, lhs=result, rhs=self.parse_shift())
            elif self.accept('instanceof'):
                typ = self.parse_generic_type_or_array()
                result = tree.TypeTest(type=typ, expr=result)
            else:
                return result

    def parse_shift(self):
        result = self.parse_add()
        while True:
            if self.accept('<<'):
                result = tree.BinaryExpression(op='<<', lhs=result, rhs=self.parse_add())
            else:
                token1 = self.token
                if token1.string == '>':
                    token2 = self.tokens.look(1)
                    if token2.string == '>' and token2.start == token1.end:
                        token3 = self.tokens.look(2)
                        if token3.string == '>' and token3.start == token2.end:
                            self.next()
                            self.next()
                            self.next()
                            result = tree.BinaryExpression(op='>>>', lhs=result, rhs=self.parse_add())
                        else:
                            result = tree.BinaryExpression(op='>>', lhs=result, rhs=self.parse_add())
                    else:
                        return result
                else:
                    return result

    def parse_add(self):
        return self.parse_binary_expr(self.parse_mul, ('+', '-'))

    def parse_mul(self):
        return self.parse_binary_expr(self.parse_unary, ('*', '/', '%'))

    def parse_unary(self):
        if self.would_accept(tree.UnaryExpression.OPS):
            op = self.token.string
            self.next()
            return tree.UnaryExpression(op=op, expr=self.parse_unary())

        elif self.would_accept(('++', '--')):
            op = self.token.string
            self.next()
            return tree.IncrementExpression(op=op, prefix=True, expr=self.parse_postfix())

        else:
            return self.parse_cast()

    def parse_cast(self):
        if self.would_accept('('):
            try:
                with self.tokens:
                    self.next() # skip past the '(' token
                    typ = self.parse_cast_type()
                    self.require(')')
                    if self.would_accept('(') or self.would_accept(NAME, '->'):
                        try:
                            with self.tokens:
                                expr = self.parse_lambda()
                        except JavaSyntaxError:
                            expr = self.parse_postfix()
                            if self.would_accept(('++', '--')):
                                op = self.token.string
                                self.next()
                                expr = tree.IncrementExpression(op=op, prefix=False, expr=expr)
                    else:
                        expr = self.parse_cast()
                    return tree.CastExpression(type=typ, expr=expr)
            except JavaSyntaxError:
                pass
        result = self.parse_postfix()
        if self.would_accept(('++', '--')):
            op = self.token.string
            self.next()
            result = tree.IncrementExpression(op=op, prefix=False, expr=result)
        return result

    def parse_postfix(self):
        result = self.parse_primary()
        while True:
            if self.would_accept('.'):
                result = self.parse_dot_expr(result)

            elif self.accept('['):
                index = self.parse_expr()
                self.require(']')
                result = tree.IndexExpression(indexed=result, index=index)

            elif self.would_accept('::'):
                result = self.parse_ref_expr(result)

            else:
                return result

    def parse_ref_expr(self, object):
        self.require('::')
        if self.accept('new'):
            return tree.MethodReference(name='new', object=object)
        else:
            return tree.MethodReference(name=self.parse_name(), object=object)

    def parse_dot_expr(self, object):
        self.require('.')
        if self.would_accept('new'):
            creator: tree.ClassCreator = self.parse_creator(allow_array=False)
            creator.object = object
            return creator

        elif self.accept('this'):
            if self.would_accept('('):
                args = self.parse_args()
                if not self.would_accept(NEWLINE):
                    self.require(NEWLINE) # raises error
                return tree.ThisCall(object=object, args=args)
            return tree.This(object=object)

        elif self.accept('super'):
            if self.would_accept('('):
                args = self.parse_args()
                if not self.would_accept(NEWLINE):
                    self.require(NEWLINE) # raises error
                return tree.SuperCall(object=object, args=args)
            return tree.Super(object=object)

        elif self.would_accept(NAME):
            name = self.parse_name()
            if self.would_accept('('):
                args = self.parse_args()
                return tree.FunctionCall(object=object, name=name, args=args)

            else:
                return tree.MemberAccess(object=object, name=name)

        elif self.would_accept('<'):
            typeargs = self.parse_type_args()
            if self.accept('this'):
                args = self.parse_args()
                if not self.would_accept(NEWLINE):
                    self.require(NEWLINE) # raises error
                return tree.ThisCall(object=object, args=args, typeargs=typeargs)
            elif self.accept('super'):
                args = self.parse_args()
                if not self.would_accept(NEWLINE):
                    self.require(NEWLINE) # raises error
                return tree.SuperCall(object=object, args=args, typeargs=typeargs)
            name = self.parse_name()
            args = self.parse_args()
            return tree.FunctionCall(object=object, name=name, args=args, typeargs=typeargs)

        else:
            raise JavaSyntaxError(f"expected NAME, 'this', 'super', 'new', or '<' here", got=self.token, at=self.position())
        
    def parse_args(self):
        self.require('(')
        args = []
        if not self.would_accept(')'):
            args.append(self.parse_arg())
            while self.accept(','):
                args.append(self.parse_arg())
        self.require(')')

        return args

    def parse_arg(self): return self.parse_expr()

    def parse_primary(self):
        if self.would_accept(NUMBER):
            result = tree.Literal(self.token.string)
            self.next()
        elif self.would_accept(STRING):
            import ast, re
            string = ast.literal_eval(self.token.string)
            assert isinstance(string, str)
            string = repr(string)           
            string = string[string.index(string[-1])+1:-1]
            string = re.sub(r"((?:\\\\)*)\\x([a-fA-F0-9]{2})", R'\1\\u00\2', string)
            result = tree.Literal('"' + string.replace('"', R'\"').replace(R"\'", "'") + '"')
            self.next()

        elif self.would_accept(CHAR):
            import ast, re
            char = ast.literal_eval(self.token.string)
            char = repr(char)[1:-1]
            char = re.sub(r"((?:\\\\)*)\\x([a-fA-F0-9]{2})", R'\1\\u00\2', char)
            result = tree.Literal("'" + char.replace("'", R"\'").replace(R'\"', '"') + "'")
            self.next()

        elif self.accept('true'):
            result = tree.Literal('true')

        elif self.accept('false'):
            result = tree.Literal('false')

        elif self.accept('null'):
            result = tree.NullLiteral()

        elif self.would_accept('this'):
            result = self.parse_primary_this()

        elif self.would_accept('super'):
            result = self.parse_primary_super()

        elif self.would_accept('switch'):
            result = self.parse_switch_expr()

        elif self.accept('void'):
            self.require('.', 'class')
            result = tree.TypeLiteral(type=tree.VoidType())

        elif self.would_accept(tree.PrimitiveType.VALUES):
            typ = tree.PrimitiveType(name=self.token.string)
            self.next()
            if self.would_accept('[') or self.would_accept('@'):
                dimensions = self.parse_dimensions()
                typ = tree.ArrayType(base=typ, dimensions=dimensions)
            self.require('.', 'class')
            result = tree.TypeLiteral(type=typ)

        elif self.would_accept('('):
            result = self.parse_parens()

        elif self.would_accept('['):
            result = self.parse_list_literal()

        elif self.would_accept('{'):
            result = self.parse_map_literal()

        elif self.would_accept('<'):
            typeargs = self.parse_type_args()
            name = self.parse_name()
            args = self.parse_args()
            result = tree.FunctionCall(name=name, args=args, typeargs=typeargs)

        elif self.would_accept('new'):
            result = self.parse_creator()

        elif self.would_accept(NAME):
            try:
                with self.tokens:
                    typ = self.parse_type()
                    if self.accept('.', 'class'):
                        result = tree.TypeLiteral(typ)
                    elif not isinstance(typ, tree.PrimitiveType) and (not isinstance(typ, tree.GenericType) or not typ.issimple) and self.would_accept('::'):
                        result = typ
                    else:
                        raise JavaSyntaxError('')
            except JavaSyntaxError:
                    name = self.parse_name()
                    if self.would_accept('('):
                        args = self.parse_args()
                        result = tree.FunctionCall(name=name, args=args)
                    else:
                        result = tree.MemberAccess(name=name)

        else:
            if self.token.type == NEWLINE:
                raise JavaSyntaxError("unexpected token", token=self.token, at=self.position())
            elif self.token.type == ENDMARKER:
                raise JavaSyntaxError("reached end of file while parsing", at=self.position())
            elif self.token.type in (INDENT, DEDENT):
                raise JavaSyntaxError(f"unexpected {tok_name[self.token.type].lower()}", at=self.position())
            else:
                raise JavaSyntaxError("illegal start of expression", token=self.token, at=self.position())

        return result
    
    def parse_parens(self):
        self.require('(')
        result = tree.Parenthesis(self.parse_expr())
        self.require(')')
        return result

    def parse_primary_this(self):
        self.require('this')
        if self.would_accept('('):
            args = self.parse_args()
            if not self.would_accept(';'):
                self.require(';') # raises error
            return tree.ThisCall(args=args)
        else:
            return tree.This()

    def parse_primary_super(self):
        self.require('super')
        if self.would_accept('('):
            args = self.parse_args()
            if not self.would_accept(';'):
                self.require(';') # raises error
            return tree.SuperCall(args=args)
        else:
            if not self.would_accept('.'):
                raise JavaSyntaxError("'super' must be followed by a member-access expression", token=self.token, at=self.position())
            return tree.Super()
            
    def parse_creator(self, allow_array=True):
        self.require('new')
        typeargs = self.parse_type_args_opt()
        annotations = self.parse_annotations(newlines=False)
        if not typeargs and allow_array and self.would_accept(tree.PrimitiveType.VALUES):
            typ = tree.PrimitiveType(name=self.token.string, annotations=annotations)
            self.next()
            dimensions = []
            annotations = self.parse_annotations(newlines=False)
            self.require('[')
            if self.accept(']'):
                dimensions.append(tree.DimensionExpression(annotations=annotations))
                while self.would_accept(('@', '[')):
                    annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                    self.require('[', ']')
                    dimensions.append(tree.DimensionExpression(annotations=annotations))
                init = self.parse_array_init()
                result = tree.ArrayCreator(type=typ, dimensions=dimensions, initializer=init)

            else:
                dimensions.append(tree.DimensionExpression(size=self.parse_expr(), annotations=annotations))
                self.require(']')
                while self.would_accept(('@', '[')):
                    annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                    self.require('[')
                    if self.accept(']'):
                        dimensions.append(tree.DimensionExpression(annotations=annotations))
                        break
                    dimensions.append(tree.DimensionExpression(annotations=annotations, size=self.parse_expr()))
                    self.require(']')
                while self.would_accept(('@', '[')):
                    annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                    self.require('[', ']')
                    dimensions.append(tree.DimensionExpression(annotations=annotations))
                result = tree.ArrayCreator(type=typ, dimensions=dimensions)

        else:
            typ = self.parse_generic_type()
            typ.annotations = annotations
            if not typeargs and allow_array and self.would_accept(('[', '@')):
                dimensions = []
                annotations = self.parse_annotations(newlines=False)
                self.require('[')
                if self.accept(']'):
                    dimensions.append(tree.DimensionExpression(annotations=annotations))
                    while self.would_accept(('@', '[')):
                        annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                        self.require('[', ']')
                        dimensions.append(tree.DimensionExpression(annotations=annotations))
                    init = self.parse_array_init()
                    result = tree.ArrayCreator(type=typ, dimensions=dimensions, initializer=init)
                    
                else:
                    dimensions.append(tree.DimensionExpression(size=self.parse_expr(), annotations=annotations))
                    self.require(']')
                    while self.would_accept(('@', '[')):
                        annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                        self.require('[')
                        if self.accept(']'):
                            dimensions.append(tree.DimensionExpression(annotations=annotations))
                            break
                        dimensions.append(tree.DimensionExpression(annotations=annotations, size=self.parse_expr()))
                        self.require(']')
                    while self.would_accept(('@', '[')):
                        annotations = self.parse_annotations(newlines=False) if self.would_accept('@') else []
                        self.require('[', ']')
                        dimensions.append(tree.DimensionExpression(annotations=annotations))
                    result = tree.ArrayCreator(type=typ, dimensions=dimensions)

            else:
                result = self.parse_class_creator_rest(typ, typeargs)
        
        return result

    def parse_class_creator_rest(self, type, typeargs):
        args = self.parse_args()
        if self.would_accept('{'):
            members = self.parse_class_body(self.parse_class_member)
        else:
            members = None
        if typeargs is None:
            typeargs = []
        return tree.ClassCreator(type=type, args=args, typeargs=typeargs, members=members)

    def parse_lambda(self):
        if self.would_accept(NAME):
            args = [self.parse_name()]
        else:
            if self.would_accept('(', NAME, (')', ',')):
                self.next() # skips past the '(' token
                args = [self.parse_name()]
                while self.accept(','):
                    args.append(self.parse_name())
                self.require(')')
            else:
                args = self.parse_parameters(allow_this=False)

        self.require('->')

        if self.would_accept('{'):
            body = self.parse_lambda_block_body()
        else:
            body = self.parse_expr()

        return tree.Lambda(params=args, body=body)

    def parse_lambda_block_body(self):
        return self.parse_block()

    def parse_switch_expr(self):
        self.require('switch')
        condition = self.parse_condition()
        self.require('{')
        cases = []
        while not self.would_accept(('}', ENDMARKER)):
            cases.append(self.parse_case())
        self.require('}')
        return tree.Switch(condition=condition, cases=cases)

    def parse_list_literal(self):
        raise JavaSyntaxError("illegal start of expression", token=self.token, at=self.position())
        return False

    def parse_map_literal(self):
        raise JavaSyntaxError("illegal start of expression", token=self.token, at=self.position())
        return False

    #endregion Expressions

def parse_file(file, parser: Type[JavaParser]=JavaParser) -> tree.CompilationUnit:
    assert check_argument_types()
    assert issubclass(parser, JavaParser)
    return parser(tokenize(file.readline), getattr(file, 'name', '<unknown source>')).parse_compilation_unit()

def parse_str(s: Union[str, bytes, bytearray], encoding='utf-8', parser: Type[JavaParser]=JavaParser) -> tree.CompilationUnit:
    assert check_argument_types()
    assert issubclass(parser, JavaParser)
    if isinstance(s, str):
        s = bytes(s, encoding)        
    return parser(tokenize(io.BytesIO(s).readline), '<string>').parse_compilation_unit()
