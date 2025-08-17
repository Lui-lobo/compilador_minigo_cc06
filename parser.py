# parser.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from lexer import Lexer, Token, TokenType
import go_ast as A  # seu módulo de AST (não é o stdlib "ast")

# ------------------------------------------------------------
# Representação de erro sintático
# ------------------------------------------------------------

@dataclass
class ParseError:
    line: int
    column: int
    message: str

# ------------------------------------------------------------
# Parser (descida recursiva + Pratt para expressões)
# ------------------------------------------------------------

class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.tokens: List[Token] = lexer.tokenize()
        self.pos: int = 0
        self.errors: List[ParseError] = []

    # ------------- helpers básicos -------------

    def _pos_of_expr(self, e):
        if hasattr(e, "line") and hasattr(e, "column"):
            return e.line, e.column
        if isinstance(e, A.NameExpr) and hasattr(e, "ident"):
            return e.ident.line, e.ident.column
        tok = self._current()
        return tok.line, tok.column

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, k: int = 0) -> Token:
        i = self.pos + k
        if i >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[i]

    def _at(self, tt: TokenType) -> bool:
        return self._current().type == tt

    def _match(self, *types: TokenType) -> bool:
        if self._current().type in types:
            self.pos += 1
            return True
        return False

    def _expect(self, tt: TokenType, msg: str) -> Token:
        tok = self._current()
        if tok.type == tt:
            self.pos += 1
            return tok
        self._error(tok, msg + f" (esperado {tt.name}, encontrado {tok.type.name})")
        # não consome; deixa o chamador decidir como se recuperar
        return tok

    def _error(self, tok: Token, message: str):
        self.errors.append(ParseError(tok.line, tok.column, message))

    def _synchronize(self, stop_types: List[TokenType]):
        # avança até encontrar um token “seguro” ou EOF
        while self._current().type not in stop_types and self._current().type != TokenType.EOF:
            self.pos += 1

    # ------------- parsing de alto nível -------------

    def parse_program(self) -> Optional[A.Program]:
        # program := "package" IDENT ";"? decl*
        if not self._match(TokenType.PACKAGE):
            self._error(self._current(), "programa deve iniciar com 'package'")
            return None

        name_tok = self._expect(TokenType.IDENT, "nome do pacote após 'package'")
        package = A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column)

        # opcionalmente aceitar ';' após "package main"
        self._match(TokenType.SEMICOLON)

        decls: List[A.Decl] = []
        while not self._at(TokenType.EOF):
            if self._match(TokenType.FUNC):
                d = self._func_decl()
                if d:
                    decls.append(d)
            elif self._match(TokenType.VAR):
                d = self._var_decl(expect_semicolon=True)
                if d:
                    decls.append(d)
            elif self._at(TokenType.EOF):
                break
            else:
                # token inesperado em nível superior
                self._error(self._current(), "declaração esperada ('func' ou 'var')")
                self._synchronize([TokenType.FUNC, TokenType.VAR, TokenType.EOF])

        return A.Program(package, decls)

    # ------------- declarações -------------

    def _var_decl(self, expect_semicolon: bool) -> Optional[A.VarDecl]:
        # varDecl := IDENT type? ('=' expr)? ';'?
        name_tok = self._expect(TokenType.IDENT, "identificador da variável")
        type_name: Optional[A.TypeName] = None
        init_expr: Optional[A.Expr] = None

        # tipo opcional (int/float64/bool/string)
        if self._current().type in (
            TokenType.INT_TYPE,
            TokenType.FLOAT64_TYPE,
            TokenType.BOOL_TYPE,
            TokenType.STRING_TYPE,
        ):
            t = self._current()
            self.pos += 1
            type_name = A.TypeName(t.lexeme, t.line, t.column)

        # inicialização opcional
        if self._match(TokenType.ASSIGN):
            init_expr = self._expression()

        if expect_semicolon:
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após declaração de variável")

        return A.VarDecl(
            name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
            type_name=type_name,
            init=init_expr,
            line=name_tok.line,
            column=name_tok.column,
        )

    def _func_decl(self) -> Optional[A.FuncDecl]:
        # funcDecl := "func" IDENT "(" paramList? ")" resultType? block
        name_tok = self._expect(TokenType.IDENT, "nome da função")
        self._expect(TokenType.LPAREN, "abrir parênteses da lista de parâmetros")

        params: List[A.Param] = []
        if not self._at(TokenType.RPAREN):
            params = self._param_list()
        self._expect(TokenType.RPAREN, "fechar parênteses da lista de parâmetros")

        result: Optional[A.TypeName] = None
        if self._current().type in (
            TokenType.INT_TYPE,
            TokenType.FLOAT64_TYPE,
            TokenType.BOOL_TYPE,
            TokenType.STRING_TYPE,
        ):
            t = self._current()
            self.pos += 1
            result = A.TypeName(t.lexeme, t.line, t.column)

        body = self._block_stmt()
        return A.FuncDecl(
            name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
            params=params,
            result=result,
            body=body,
            line=name_tok.line,
            column=name_tok.column,
        )

    def _param_list(self) -> List[A.Param]:
        # paramList := (IDENT type) (',' IDENT type)*
        params: List[A.Param] = []
        while True:
            name_tok = self._expect(TokenType.IDENT, "nome do parâmetro")
            type_tok = self._current()
            if type_tok.type not in (
                TokenType.INT_TYPE,
                TokenType.FLOAT64_TYPE,
                TokenType.BOOL_TYPE,
                TokenType.STRING_TYPE,
            ):
                self._error(type_tok, "tipo do parâmetro esperado (int/float64/bool/string)")
            else:
                self.pos += 1

            params.append(
                A.Param(
                    name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                    type_name=A.TypeName(type_tok.lexeme, type_tok.line, type_tok.column),
                )
            )
            if not self._match(TokenType.COMMA):
                break
        return params

    # ------------- statements -------------

    def _block_stmt(self) -> A.BlockStmt:
        lbrace = self._expect(TokenType.LBRACE, "abrir bloco '{'")
        stmts: List[A.Stmt] = []

        while not self._at(TokenType.RBRACE) and not self._at(TokenType.EOF):
            stmts.append(self._statement())

        self._expect(TokenType.RBRACE, "fechar bloco '}'")
        return A.BlockStmt(stmts, lbrace.line, lbrace.column)

    def _statement(self) -> A.Stmt:
        # ordem importa: checar palavras-chave primeiro
        if self._match(TokenType.VAR):
            # var dentro de bloco
            decl = self._var_decl(expect_semicolon=True)
            return decl  # em Python, usaremos VarDecl também como Stmt

        if self._match(TokenType.IF):
            return self._if_stmt()

        if self._match(TokenType.FOR):
            return self._for_stmt()

        if self._match(TokenType.RETURN):
            stmt = self._return_stmt()
            # o ';' é consumido por _statement() como nos demais statements
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após 'return'")
            return stmt

        # Caso geral: simpleStmt (expr/assign/incdec) + ';'
        stmt = self._simple_stmt()
        self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após statement")
        return stmt

    def _if_stmt(self) -> A.IfStmt:
        cond = self._expression()
        then_block = self._block_stmt()
        else_block = None
        if self._match(TokenType.ELSE):
            else_block = self._block_stmt()
        tok = self._peek(-1) if self.pos > 0 else self._current()
        return A.IfStmt(cond, then_block, else_block, tok.line, tok.column)
    
    def _maybe_for_init_stmt(self) -> Optional[A.Stmt]:
        """
        Reconhece (sem consumir ';'):
          - IDENT := expr        (VarDecl inferido)
          - IDENT = expr         (Assign)
          - expr                 (ExprStmt)   ex.: chamada
        Se não for nada reconhecível, retorna None (permitindo 'for ; cond ; post').
        """
        # IDENT := expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.DEFINE):
            name_tok = self._current()
            self.pos += 2
            init = self._expression()
            return A.VarDecl(
                name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                type_name=None,
                init=init,
                line=name_tok.line,
                column=name_tok.column,
            )

        # IDENT = expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.ASSIGN):
            name_tok = self._current()
            self.pos += 2
            value = self._expression()
            expr = A.AssignExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                value=value,
                line=name_tok.line,
                column=name_tok.column,
            )
            return A.ExprStmt(expr, name_tok.line, name_tok.column)

        # tente expressão genérica como init (ex.: chamada)
        save = self.pos
        expr = self._expression()
        if expr:
            line, col = self._pos_of_expr(expr)
            return A.ExprStmt(expr, line, col)

        # nada reconhecido
        self.pos = save
        return None

    def _for_stmt(self) -> A.ForStmt:
        """
        Suporta:
          - for { ... }
          - for cond { ... }
          - for init ; cond ; post { ... }
        """
        init = None
        cond = None
        post = None

        # Caso 'for {' → bloco infinito
        if self._at(TokenType.LBRACE):
            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)

        # Tente reconhecer 'init ; cond ; post' (init sem consumir ';' aqui)
        save_pos = self.pos
        maybe_init = self._maybe_for_init_stmt()

        if self._match(TokenType.SEMICOLON):
            init = maybe_init  # pode ser None (for ; cond ; post)

            # cond opcional
            if not self._at(TokenType.SEMICOLON):
                cond = self._expression()
            self._expect(TokenType.SEMICOLON, "ponto-e-vírgula após condição do for")

            # post opcional
            if not self._at(TokenType.LBRACE):
                post = self._post_stmt()

            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)
        else:
            # Não era a forma com dois ';' → trata como 'for cond { ... }'
            # volta para before init e parseia uma expressão como condição
            self.pos = save_pos
            if not self._at(TokenType.LBRACE):
                cond = self._expression()
            body = self._block_stmt()
            tok = self._peek(-1) if self.pos > 0 else self._current()
            return A.ForStmt(init, cond, post, body, tok.line, tok.column)


    def _post_stmt(self) -> A.Stmt:
        # pós do for: qualquer expressão simples (incl. i++, i--, i = i + 1, chamada)
        expr = self._expression()
        return A.ExprStmt(expr, expr.line, expr.column)

    def _return_stmt(self) -> A.ReturnStmt:
        """
        returnStmt := 'return' expr?
        (o ';' é consumido por _statement)
        """
        tok = self._peek(-1) if self.pos > 0 else self._current()

        if self._at(TokenType.SEMICOLON) or self._at(TokenType.RBRACE):
            return A.ReturnStmt(None, tok.line, tok.column)

        expr = self._expression()
        return A.ReturnStmt(expr, tok.line, tok.column)

    def _simple_stmt(self) -> A.Stmt:
        # short var: IDENT := expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.DEFINE):
            name_tok = self._current()
            self.pos += 2  # consome IDENT e :=
            init = self._expression()
            # Representamos como VarDecl com type=None (inferência no semântico)
            return A.VarDecl(
                name=A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                type_name=None,
                init=init,
                line=name_tok.line,
                column=name_tok.column,
            )
    
        # assign: IDENT = expr
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type == TokenType.ASSIGN):
            name_tok = self._current()
            self.pos += 2  # IDENT '='
            value = self._expression()
            expr = A.AssignExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                value=value,
                line=name_tok.line,
                column=name_tok.column,
            )
            line, col = name_tok.line, name_tok.column
            return A.ExprStmt(expr, line, col)
    
        # inc/dec: IDENT ++/--
        if (self._current().type == TokenType.IDENT and
            self._peek(1).type in (TokenType.INC, TokenType.DEC)):
            name_tok = self._current(); op_tok = self._peek(1)
            self.pos += 2
            expr = A.IncDecExpr(
                target=A.NameExpr(A.Identifier(name_tok.lexeme, name_tok.line, name_tok.column),
                                  name_tok.line, name_tok.column),
                op="++" if op_tok.type == TokenType.INC else "--",
                line=name_tok.line,
                column=name_tok.column,
            )
            return A.ExprStmt(expr, name_tok.line, name_tok.column)
    
        # fallback: expressão genérica
        expr = self._expression()
        line, col = self._pos_of_expr(expr)
        return A.ExprStmt(expr, line, col)


    # ------------- expressões (Pratt) -------------

    # precedências (menor -> maior)
    # 1: ||   2: &&   3: == !=   4: < <= > >=
    # 5: + -   6: * / %
    PRECEDENCE = {
        "OR": 1,
        "AND": 2,
        "EQ": 3, "NOT_EQ": 3,
        "LT": 4, "LTE": 4, "GT": 4, "GTE": 4,
        "PLUS": 5, "MINUS": 5,
        "ASTERISK": 6, "SLASH": 6, "MOD": 6,
    }

    def _precedence_of(self, tok: Token) -> int:
        return self.PRECEDENCE.get(tok.type.name, 0)

    def _expression(self, min_prec: int = 1) -> A.Expr:
        """
        expressão com climbing de precedência + pós-fixos (call e seletor).
        """
        expr = self._prefix()

        # pós-fixos de maior precedência: chamada () e seletor .
        while True:
            # chamada: expr '(' arglist? ')'
            if self._match(TokenType.LPAREN):
                args = []
                if not self._at(TokenType.RPAREN):
                    while True:
                        args.append(self._expression())
                        if not self._match(TokenType.COMMA):
                            break
                rp = self._expect(TokenType.RPAREN, "fechar chamada ')'")
                expr = A.CallExpr(expr, args, rp.line, rp.column)
                continue

            # seletor: expr '.' IDENT  (ex.: fmt.Println)
            if self._match(TokenType.DOT):
                attr = self._expect(TokenType.IDENT, "nome após '.'")
                expr = A.SelectorExpr(
                    expr,
                    A.Identifier(attr.lexeme, attr.line, attr.column),
                    attr.line,
                    attr.column,
                )
                continue

            break

        # operadores binários infix, respeitando precedência
        while True:
            tok = self._current()
            prec = self._precedence_of(tok)
            if prec < min_prec or prec == 0:
                break
            self.pos += 1  # consome o operador
            right = self._expression(prec + 1)
            expr = A.BinaryExpr(expr, tok.lexeme or tok.type.name, right, tok.line, tok.column)

        return expr

    def _prefix(self) -> A.Expr:
        tok = self._current()

        # literais
        if self._match(TokenType.INT):
            return A.IntegerLit(int(tok.lexeme), tok.line, tok.column)
        if self._match(TokenType.FLOAT):
            return A.FloatLit(float(tok.lexeme), tok.line, tok.column)
        if self._match(TokenType.STRING):
            return A.StringLit(tok.lexeme, tok.line, tok.column)
        if self._match(TokenType.TRUE):
            return A.BoolLit(True, tok.line, tok.column)
        if self._match(TokenType.FALSE):
            return A.BoolLit(False, tok.line, tok.column)

        # identificador
        if self._match(TokenType.IDENT):
            ident = A.Identifier(tok.lexeme, tok.line, tok.column)
            return A.NameExpr(ident, tok.line, tok.column)  # se você adotou a opção A

        # unários: !  -
        if self._match(TokenType.BANG):
            right = self._expression(7)  # maior que qualquer binário
            return A.UnaryExpr("!", right, tok.line, tok.column)
        if self._match(TokenType.MINUS):
            right = self._expression(7)
            return A.UnaryExpr("-", right, tok.line, tok.column)

        # parênteses
        if self._match(TokenType.LPAREN):
            expr = self._expression()
            self._expect(TokenType.RPAREN, "fechar ')'")
            return expr

        # erro de expressão
        self._error(tok, f"expressão inesperada: {tok.type.name}")
        self.pos += 1  # evita loop
        return A.IntegerLit(0, tok.line, tok.column)
