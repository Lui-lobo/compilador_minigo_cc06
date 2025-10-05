package main

/* Teste de escopos e sombreamento */
func main() {
    var x int = 10;    // variável no escopo externo

    if true {
        var x int = 20;    // nova variável no escopo interno (sombra a externa)
        fmt.Println(x);    // deve imprimir 20
    }

    fmt.Println(x);        // deve imprimir 10 (a variável externa)
}
