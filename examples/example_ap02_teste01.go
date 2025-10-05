package main

/* Programa que calcula o fatorial de um número */
func main() {
    var fat int = 1;      // fatorial inicializado em 1
    var num int = 5;      // simula leitura (read(num))
    var cont int = 2;     // contador inicial

    for cont <= num {
        fat = fat * cont;
        cont = cont + 1;
    }

    fmt.Println(fat);     // imprime resultado
}
