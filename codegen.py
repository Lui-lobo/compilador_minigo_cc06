# codegen.py
from __future__ import annotations
from typing import List
import go_ast as A
from semantics import VarSymbol, SemanticAnalyzer

class CodeGenerator:
    def __init__(self, analyzer: SemanticAnalyzer):
        self.analyzer = analyzer
        self.code: List[str] = []
        self._label_count = 0

        # Pilha de escopos locais (variáveis e endereços)
        self.scopes: list[dict[str, int]] = [{}]
        self.next_addr = 0  # contador global de endereços locais

    # -------------------------------
    # Utilitários básicos
    # -------------------------------
    def next_label(self) -> str:
        self._label_count += 1
        return f"L{self._label_count}"

    def emit(self, instr: str):
        self.code.append(instr)

    # Controle de escopo
    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def declare_var(self, name: str) -> int:
        """Declara variável local no escopo atual"""
        addr = self.next_addr
        self.next_addr += 1
        self.scopes[-1][name] = addr
        self.emit("\tAMEM 1")
        return addr

    def lookup_addr(self, name: str) -> int:
        """Procura variável do escopo mais interno até o global"""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        # busca em globais (semântica)
        sym = self.analyzer.scope.lookup(name)
        if isinstance(sym, VarSymbol):
            # globais começam do endereço 0
            return list(self.analyzer.scope.syms.keys()).index(name)
        if name in ("fmt", "Println"):
            return 0  # ignora pseudo-nomes
        raise RuntimeError(f"Variável {name} não declarada")

    # -------------------------------
    # Geração principal
    # -------------------------------
    def generate(self, program: A.Program) -> List[str]:
        globals_count = sum(
            1 for sym in self.analyzer.scope.syms.values() if isinstance(sym, VarSymbol)
        )
        if globals_count:
            self.emit(f"\tAMEM {globals_count}")

        for d in program.decls:
            if isinstance(d, A.FuncDecl):
                self.func_decl(d)
        return self.code

    # -------------------------------
    # Declarações e blocos
    # -------------------------------
    def func_decl(self, f: A.FuncDecl):
        self.scopes = [{}]
        self.next_addr = 0
        self.emit(f"{f.name.name}: NADA")
        self.block(f.body, is_root=True)
        self.emit("\tRETU")

    def block(self, b: A.BlockStmt, is_root: bool = False):
        """Novo escopo para cada bloco (exceto o corpo da função)"""
        self.push_scope()
        for s in b.stmts:
            self.stmt(s)

        local_count = len(self.scopes[-1])
        # ⚠️ Só desaloca se não for o escopo raiz da função
        if local_count > 0 and not is_root:
            self.emit(f"\tDMEM {local_count}")
        self.pop_scope()

    # -------------------------------
    # Statements
    # -------------------------------
    def stmt(self, s: A.Stmt):
        if isinstance(s, A.VarDecl):
            addr = self.declare_var(s.name.name)
            if s.init:
                self.expr(s.init)
                self.emit(f"\tARMZ {addr}")
            return

        if isinstance(s, A.AssignExpr):
            addr = self.lookup_addr(s.target.ident.name)
            self.expr(s.value)
            self.emit(f"\tARMZ {addr}")
            return

        if isinstance(s, A.ExprStmt):
            # simula fmt.Println
            if isinstance(s.expr, A.CallExpr) and isinstance(s.expr.callee, A.SelectorExpr):
                if s.expr.args:
                    self.expr(s.expr.args[0])
                    self.emit("\tESCRV")
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
        label_else = self.next_label()
        label_end = self.next_label()

        self.expr(s.cond)
        self.emit(f"\tDSVF {label_else}")

        self.block(s.then_block)
        self.emit(f"\tDSVS {label_end}")

        self.emit(f"{label_else}: NADA")
        if s.else_block:
            self.block(s.else_block)
        self.emit(f"{label_end}: NADA")

    def for_stmt(self, s: A.ForStmt):
        label_start = self.next_label()
        label_end = self.next_label()
        self.emit(f"{label_start}: NADA")

        if s.cond:
            self.expr(s.cond)
            self.emit(f"\tDSVF {label_end}")

        self.block(s.body)
        if s.post:
            self.stmt(s.post)
        self.emit(f"\tDSVS {label_start}")
        self.emit(f"{label_end}: NADA")

    # -------------------------------
    # Expressões
    # -------------------------------
    def expr(self, e: A.Expr):
        if isinstance(e, A.IntegerLit):
            self.emit(f"\tCRCT {e.value}")

        elif isinstance(e, A.BoolLit):
            val = 1 if e.value else 0
            self.emit(f"\tCRCT {val}")

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
