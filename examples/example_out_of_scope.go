package main

var global int = 5;

func foo() {
    var local int = 10;
}

func main() {
    foo();
    fmt.Println(local); // ERRO: variável local não visível fora de foo()
}
