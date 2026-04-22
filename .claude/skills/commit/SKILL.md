---
name: commit
description: Stage y commit de los cambios con un mensaje siguiendo Conventional Commits.
disable-model-invocation: true
allowed-tools: Bash(git add *) Bash(git commit *) Bash(git status *) Bash(git diff *)
---

Crea un commit de los cambios actules:

1.-. Ejecuta `git status` para ver qué cambió.
2.- Ejecuta `git diff --staged` y `git diff` para entender los cambios.
3.- Stage los archivos relevantes con `git add`
4.- Genera un commit message siguiendo Conventional Commits:
    - `feat`: nueva funcionalidad
    - `fix`: bug fix
    - `refactor`: cambio de código sin cambios de comportamientos
    - `docs`: cambios en la documentación
    - `test`: cambios relacionados con pruebas
    - `chore`: tareas de mantenimiento
5.- Ejecuta `git commit -m "tipo: descripción breve"` para crear el commit

El mensaje debe de ser claro, en inglés, y explicar el "por qué" del cambio cuando aplique.