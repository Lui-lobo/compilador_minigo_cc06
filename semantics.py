# semantics.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

import go_ast as A

# -------------------------
# Tipos
# -------------------------

@dataclass(frozen=True)
class Type:
    name: str  # "int", "float64", "bool", "string", "void", "invalid"

INT = Type("int")
FLOAT = Type("float64")
BOOL = Type("bool")
STRING = Type("string")
VOID = Type("void")
INVALID = Type("invalid")

def type_from_typename(tn: Optional[A.TypeName]) -> Type:
    if tn is None: return VOID  # usado para "sem anotação" em locais onde não é requerido
    n = tn.name
    if n == "int": return INT
    if n == "float64": return FLOAT
    if n == "bool": return BOOL
    if n == "string": return STRING
    return INVALID

def is_numeric(t: Type) -> bool:
    return t in (INT, FLOAT)

def common_numeric(l: Type, r: Type) -> Type:
    # regra simples: int + float64 => float64
    if l == FLOAT or r == FLOAT: return FLOAT
    if l == INT and r == INT: return INT
    return INVALID

# -------------------------
# Símbolos / Escopos
# -------------------------

@dataclass
class VarSymbol:
    name: str
    type: Type
    decl: A.VarDecl

@dataclass
class FuncSymbol:
    name: str
    params: List[Type]
    result: Type
    decl: A.FuncDecl

class Scope:
    def __init__(self, parent: Optional["Scope"]=None):
        self.parent = parent
        self.syms: Dict[str, object] = {}
    def define(self, name: str, sym: object) -> bool:
        if name in self.syms: return False
        self.syms[name] = sym
        return True
    def lookup(self, name: str) -> Optional[object]:
        s: Optional[Scope] = self
        while s:
            if name in s.syms: return s.syms[name]
            s = s.parent
        return None

# -------------------------
# Erros
# -------------------------

@dataclass
class SemaError:
    line: int
    column: int
    message: str

# -------------------------
# Analisador Semântico
# -------------------------

class SemanticAnalyzer:
    def __init__(self):
        self.errors: List[SemaError] = []
        self.types: Dict[int, Type] = {}  # id(node) -> Type
        self.scope = Scope(None)
        self.current_func: Optional[FuncSymbol] = None

        # builtin simples (opcional): print(...): void
        self.scope.define("print", FuncSymbol("print", params=[], result=VOID, decl=None))  # varargs tolerados

    # ---------- utils ----------

    def _note_type(self, node, t: Type):
        if node is not None:
            self.types[id(node)] = t

    def _err(self, node, msg: str):
        line = getattr(node, "line", 0)
        col = getattr(node, "column", 0)
        self.errors.append(SemaError(line, col, msg))

    def _assert_assignable(self, dst: Type, src: Type, node):
        # regra simples: numéricas permitem int->float64; iguais são ok
        if dst == src: return
        if dst == FLOAT and src == INT: return
        self._err(node, f"tipo incompatível: não é possível atribuir {src.name} em {dst.name}")

    # ---------- entrada ----------

    def analyze(self, program: A.Program) -> bool:
        # 1) pacote/escopo global já existe; coletar declarações topo
        for d in program.decls:
            if isinstance(d, A.VarDecl):
                self._declare_global_var(d)
            elif isinstance(d, A.FuncDecl):
                self._declare_func(d)

        # 2) checar corpo de funções e var inits de topo
        for d in program.decls:
            if isinstance(d, A.VarDecl):
                self._check_vardecl(d, in_block=False)
            elif isinstance(d, A.FuncDecl):
                self._check_func(d)
        return not self.errors

    # ---------- declarações topo ----------

    def _declare_global_var(self, d: A.VarDecl):
        # se tiver tipo, ok; se não tiver, vamos inferir depois ao checar init
        # evitar redeclaração
        t = type_from_typename(d.type_name) if d.type_name else VOID
        # placeholder de tipo VOID até inferir
        sym = VarSymbol(d.name.name, t, d)
        if not self.scope.define(sym.name, sym):
            self._err(d, f"variável global '{sym.name}' redeclarada")

    def _declare_func(self, f: A.FuncDecl):
        params: List[Type] = []
        for p in f.params:
            pt = type_from_typename(p.type_name)
            if pt == INVALID:
                self._err(p, f"tipo de parâmetro inválido: {p.type_name.name}")
            params.append(pt)
        res = type_from_typename(f.result) if f.result else VOID
        sym = FuncSymbol(f.name.name, params, res, f)
        if not self.scope.define(sym.name, sym):
            self._err(f, f"função '{sym.name}' redeclarada")

    # ---------- checagem de declarações ----------

    def _check_func(self, f: A.FuncDecl):
        # abre escopo de função
        func_sym = self.scope.lookup(f.name.name)
        assert isinstance(func_sym, FuncSymbol)
        prev = self.current_func
        self.current_func = func_sym
        fn_scope = Scope(self.scope)
        # params entram no escopo
        for (p, t) in zip(f.params, func_sym.params):
            if not fn_scope.define(p.name.name, VarSymbol(p.name.name, t, None)):
                self._err(p, f"parâmetro '{p.name.name}' duplicado")
        # corpo
        saved = self.scope
        self.scope = fn_scope
        self._check_block(f.body)
        self.scope = saved
        self.current_func = prev

    def _check_block(self, b: A.BlockStmt):
        blk = Scope(self.scope)
        saved = self.scope
        self.scope = blk
        for s in b.stmts:
            self._check_stmt(s)
        self.scope = saved

    def _check_stmt(self, s: A.Stmt):
        if isinstance(s, A.VarDecl):
            self._check_vardecl(s, in_block=True)
            return
        if isinstance(s, A.ExprStmt):
            self._type_of_expr(s.expr)  # só para validar
            return
        if isinstance(s, A.ReturnStmt):
            self._check_return(s)
            return
        if isinstance(s, A.IfStmt):
            tcond = self._type_of_expr(s.cond)
            if tcond != BOOL:
                self._err(s.cond, f"condição do if deve ser bool, obtido {tcond.name}")
            self._check_block(s.then_block)
            if s.else_block:
                self._check_block(s.else_block)
            return
        if isinstance(s, A.ForStmt):
            if s.init: self._check_stmt(s.init)
            if s.cond:
                tcond = self._type_of_expr(s.cond)
                if tcond != BOOL:
                    self._err(s.cond, f"condição do for deve ser bool, obtido {tcond.name}")
            if s.post: self._check_stmt(s.post)
            self._check_block(s.body)
            return
        if isinstance(s, A.AssignStmt):
            # (se usarem AssignStmt diretamente)
            lt = self._type_of_expr(s.lhs)
            rt = self._type_of_expr(s.rhs)
            self._assert_assignable(lt, rt, s)
            return
        # fallback
        # (outros statements não esperados no subset)
        return

    def _check_vardecl(self, d: A.VarDecl, in_block: bool):
        declared = self.scope.lookup(d.name.name)
        if in_block:
            # no bloco, impedir sombra duplicada imediata
            if isinstance(declared, VarSymbol) and declared.decl and declared.decl is not d and d.name.name in self.scope.syms:
                self._err(d, f"variável '{d.name.name}' redeclarada no mesmo escopo")
        # tipo declarado (se houver)
        declared_type = type_from_typename(d.type_name) if d.type_name else None
        if d.init is None and declared_type is None:
            self._err(d, f"não é possível inferir tipo de '{d.name.name}' sem inicializador")
            vtype = INVALID
        else:
            init_type = self._type_of_expr(d.init) if d.init is not None else None
            if declared_type is not None and init_type is not None:
                self._assert_assignable(declared_type, init_type, d)
                vtype = declared_type
            elif declared_type is not None:
                vtype = declared_type
            else:
                vtype = init_type
        # registrar/atualizar símbolo
        sym_here = VarSymbol(d.name.name, vtype or INVALID, d)
        # se já existia placeholder global, sobrescreve no escopo atual
        self.scope.syms[d.name.name] = sym_here

    def _check_return(self, r: A.ReturnStmt):
        expected = self.current_func.result if self.current_func else VOID
        if r.value is None:
            if expected != VOID:
                self._err(r, f"função espera retorno {expected.name}, mas 'return' vazio encontrado")
            return
        got = self._type_of_expr(r.value)
        self._assert_assignable(expected, got, r)

    # ---------- Expressões ----------

    def _type_of_expr(self, e: A.Expr) -> Type:
        if isinstance(e, A.IntegerLit):
            self._note_type(e, INT); return INT
        if isinstance(e, A.FloatLit):
            self._note_type(e, FLOAT); return FLOAT
        if isinstance(e, A.StringLit):
            self._note_type(e, STRING); return STRING
        if isinstance(e, A.BoolLit):
            self._note_type(e, BOOL); return BOOL

        if isinstance(e, A.NameExpr):
            sym = self.scope.lookup(e.ident.name)
            if isinstance(sym, VarSymbol):
                self._note_type(e, sym.type); return sym.type
            if isinstance(sym, FuncSymbol):
                # referência a função (ex.: passar função como valor não suportado)
                self._err(e, f"uso de nome de função '{sym.name}' como valor não suportado")
                self._note_type(e, INVALID); return INVALID
            self._err(e, f"identificador não declarado: {e.ident.name}")
            self._note_type(e, INVALID); return INVALID

        if isinstance(e, A.UnaryExpr):
            rt = self._type_of_expr(e.right)
            if e.op == "!":
                if rt != BOOL: self._err(e, f"'!' requer bool, obtido {rt.name}")
                self._note_type(e, BOOL); return BOOL
            if e.op == "-":
                if not is_numeric(rt): self._err(e, f"unário '-' requer numérico, obtido {rt.name}")
                self._note_type(e, rt if is_numeric(rt) else INVALID); return rt if is_numeric(rt) else INVALID

        if isinstance(e, A.BinaryExpr):
            lt = self._type_of_expr(e.left)
            rt = self._type_of_expr(e.right)
            op = e.op
            # aritméticos
            if op in {"+", "-", "*", "/", "%"}:
                if not (is_numeric(lt) and is_numeric(rt)):
                    self._err(e, f"operador '{op}' requer numéricos, obtidos {lt.name} e {rt.name}")
                    self._note_type(e, INVALID); return INVALID
                t = common_numeric(lt, rt)
                self._note_type(e, t); return t
            # relacionais
            if op in {"<", "<=", ">", ">="}:
                if not (is_numeric(lt) and is_numeric(rt)):
                    self._err(e, f"comparação '{op}' requer numéricos, obtidos {lt.name} e {rt.name}")
                self._note_type(e, BOOL); return BOOL
            # igualdade
            if op in {"==", "!="}:
                if lt != rt and not (lt == FLOAT and rt == INT) and not (lt == INT and rt == FLOAT):
                    self._err(e, f"igualdade entre tipos incompatíveis: {lt.name} vs {rt.name}")
                self._note_type(e, BOOL); return BOOL
            # lógico
            if op in {"&&", "||"}:
                if lt != BOOL or rt != BOOL:
                    self._err(e, f"operador lógico '{op}' requer bool, obtidos {lt.name} e {rt.name}")
                self._note_type(e, BOOL); return BOOL

        if isinstance(e, A.AssignExpr):
            vt = self._type_of_expr(e.value)
            if not isinstance(e.target, A.NameExpr):
                self._err(e, "atribuição requer alvo nomeado")
                self._note_type(e, INVALID); return INVALID
            sym = self.scope.lookup(e.target.ident.name)
            if not isinstance(sym, VarSymbol):
                self._err(e, f"identificador não declarado: {e.target.ident.name}")
                self._note_type(e, INVALID); return INVALID
            self._assert_assignable(sym.type, vt, e)
            self._note_type(e, sym.type); return sym.type

        if isinstance(e, A.IncDecExpr):
            t = self._type_of_expr(e.target)
            if not is_numeric(t):
                self._err(e, f"{e.op} requer alvo numérico, obtido {t.name}")
            self._note_type(e, t if is_numeric(t) else INVALID); return t if is_numeric(t) else INVALID

        if isinstance(e, A.CallExpr):
            # suportar chamadas a NameExpr (funções declaradas) e tolerar SelectorExpr como externo
            callee_type = None
            fname = None
            if isinstance(e.callee, A.NameExpr):
                fname = e.callee.ident.name
                sym = self.scope.lookup(fname)
                if isinstance(sym, FuncSymbol):
                    if len(e.args) != len(sym.params) and sym.name != "print":
                        self._err(e, f"função '{sym.name}' espera {len(sym.params)} arg(s), recebeu {len(e.args)}")
                    # checar argumentos se for print ignoramos tipos/varargs
                    for i, arg in enumerate(e.args[:len(sym.params)]):
                        at = self._type_of_expr(arg)
                        self._assert_assignable(sym.params[i], at, arg)
                    for arg in e.args[len(sym.params):]:
                        self._type_of_expr(arg)  # ainda tipa para coletar erros internos
                    self._note_type(e, sym.result); return sym.result
                else:
                    self._err(e, f"função não declarada: {fname}")
                    self._note_type(e, INVALID); return INVALID
            elif isinstance(e.callee, A.SelectorExpr):
                # tolerar chamadas de pacote externo (ex.: fmt.Println) como void sem checagem de tipos
                for arg in e.args:
                    self._type_of_expr(arg)
                self._note_type(e, VOID); return VOID

        if isinstance(e, A.SelectorExpr):
            # Sem resolução de pacotes neste subset: considere valor inválido/usado apenas como callee
            self._note_type(e, INVALID); return INVALID

        # fallback
        self._note_type(e, INVALID)
        return INVALID
