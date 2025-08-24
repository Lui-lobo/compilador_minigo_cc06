package main

/* Programa lê dois números (simulados) e encontra o maior */
func main() {
    var num1 int = 10;      // simula read(num1, num2)
    var num2 int = 20;      // simula read(num1, num2)
    var _maior int;

    if num1 > num2 {
        _maior = num1;
    } else {
        _maior = num2;
    }

    fmt.Println(_maior);
}
