# codegen.py
from __future__ import annotations
from typing import List
import go_ast as A
from semantics import VarSymbol, SemanticAnalyzer

class CodeGenerator:
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.code = []
        self._label_count = 0
        self.locals = {}        # ← novo: mapa de variáveis locais
        self.local_addr_count = 0  # contador de endereços locais

    def next_label(self) -> str:
        self._label_count += 1
        return f"L{self._label_count}"

    def emit(self, instr: str):
        self.code.append(instr)

    def generate(self, program: A.Program) -> List[str]:
        # aloca globais
        globals_count = sum(
            1 for sym in self.analyzer.scope.syms.values() if isinstance(sym, VarSymbol)
        )
        if globals_count:
            self.emit(f"\tAMEM {globals_count}")

        # percorre declarações
        for d in program.decls:
            if isinstance(d, A.FuncDecl):
                self.func_decl(d)
            elif isinstance(d, A.VarDecl):
                pass  # já alocamos no AMEM global

        return self.code

    # -------------------------------
    # Declarações / statements
    # -------------------------------
    def func_decl(self, f: A.FuncDecl):
        self.locals = {}
        self.local_addr_count = 0
        self.emit(f"{f.name.name}: NADA")

        # percorre todas as declarações locais
        for stmt in f.body.stmts:
            if isinstance(stmt, A.VarDecl):
                # aloca 1 posição por variável
                addr = self.local_addr_count
                self.locals[stmt.name.name] = addr
                self.emit(f"\tAMEM 1")

                # inicialização (se houver)
                if stmt.init:
                    self.expr(stmt.init)
                    self.emit(f"\tARMZ {addr}")

                self.local_addr_count += 1

        # agora processa o restante do corpo (if, expr, etc.)
        self.block(f.body)
        self.emit("\tRETU")

    def block(self, b: A.BlockStmt):
        for s in b.stmts:
            # ignora VarDecls do topo do bloco, pois já inicializamos acima
            if isinstance(s, A.VarDecl):
                continue
            self.stmt(s)

    def stmt(self, s: A.Stmt):
        if isinstance(s, A.VarDecl):
            # locais não tratados (opcional)
            return
        if isinstance(s, A.AssignExpr):
            addr = self.lookup_addr(s.target.ident.name)
            self.expr(s.value)
            self.emit(f"\tARMZ {addr}")
            return
        if isinstance(s, A.ExprStmt):
            # Se for chamada de função externa (fmt.Println), simula saída
            if isinstance(s.expr, A.CallExpr) and isinstance(s.expr.callee, A.SelectorExpr):
                self.expr(s.expr.args[0])
                self.emit("\tESCRV")  # simula fmt.Println como instrução de escrita
            else:
                self.expr(s.expr)
            return
        if isinstance(s, A.ReturnStmt):
            if s.value:
                self.expr(s.value)
            self.emit("\tRETU")
            return
        if isinstance(s, A.IfStmt):
            self.if_stmt(s)
            return
        if isinstance(s, A.ForStmt):
            self.for_stmt(s)
            return

    def if_stmt(self, s: A.IfStmt):
        l_else = self.next_label()
        l_end = self.next_label()
        self.expr(s.cond)
        self.emit(f"\tDSVF {l_else}")
        self.block(s.then_block)
        self.emit(f"\tDSVS {l_end}")
        self.emit(f"{l_else}: NADA")
        if s.else_block:
            self.block(s.else_block)
        self.emit(f"{l_end}: NADA")

    def for_stmt(self, s: A.ForStmt):
        l_start = self.next_label()
        l_end = self.next_label()
        self.emit(f"{l_start}: NADA")
        if s.cond:
            self.expr(s.cond)
            self.emit(f"\tDSVF {l_end}")
        self.block(s.body)
        if s.post:
            self.stmt(s.post)
        self.emit(f"\tDSVS {l_start}")
        self.emit(f"{l_end}: NADA")

    # -------------------------------
    # Expressões
    # -------------------------------

    def expr(self, e: A.Expr):
        if isinstance(e, A.IntegerLit):
            self.emit(f"\tCRCT {e.value}")
        elif isinstance(e, A.NameExpr):
            addr = self.lookup_addr(e.ident.name)
            self.emit(f"\tCRVL {addr}")
        elif isinstance(e, A.BinaryExpr):
            self.expr(e.left)
            self.expr(e.right)
            opmap = {
                "+": "SOMA",
                "-": "SUBT",
                "*": "MULT",
                "/": "DIVI",
                ">": "CMMA",
                "<": "CMME",
                ">=": "CMAG",
                "<=": "CMEG",
                "==": "CMIG",
                "!=": "CMDG",
                "&&": "CONJ",
                "||": "DISJ",
            }
            instr = opmap.get(e.op, "NADA")
            self.emit(f"\t{instr}")
        elif isinstance(e, A.UnaryExpr):
            self.expr(e.right)
            if e.op == "-":
                self.emit("\tINVR")
            elif e.op == "!":
                self.emit("\tNEGA")
        elif isinstance(e, A.AssignExpr):
            addr = self.lookup_addr(e.target.ident.name)
            self.expr(e.value)
            self.emit(f"\tARMZ {addr}")
        else:
            self.emit("\tNADA")

    # -------------------------------
    # Util
    # -------------------------------

    def lookup_addr(self, name: str) -> int:
        # procura variável local primeiro
        if name in self.locals:
            return self.locals[name]
        # procura global
        sym = self.analyzer.scope.lookup(name)
        if isinstance(sym, VarSymbol):
            return sym.addr
        # ignora pseudo-names de bibliotecas (fmt, Println)
        if name in ("fmt", "Println"):
            return 0
        raise RuntimeError(f"Variável {name} não declarada")
