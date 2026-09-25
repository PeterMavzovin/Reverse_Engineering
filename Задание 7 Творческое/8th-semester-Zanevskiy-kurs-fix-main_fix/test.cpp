#include <stdio.h>
#include <string.h>

int main(void) {
    char* pass = "my_pass";
    char* user_input = new char[10];

    scanf("%s", &user_input);

    if (strcmp(pass, user_input) != 0) {
        printf("Password incorrect!\n");
    }
    else {
        printf("Password correct!\n");
    }
    return 0;
}