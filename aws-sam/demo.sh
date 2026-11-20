#!/bin/sh
set -e
API=${1:-http://127.0.0.1:3000}
ANA="ana-$$"
BIA="bia-$$"

req() {
  printf '\n>>> [%s] %s %s %s\n' "$1" "$2" "$3" "${4:-}" >&2
  curl -s -X "$2" "$API$3" -H 'Content-Type: application/json' -H "x-membro-id: $1" ${4:+-d "$4"} | tee /dev/stderr
}
campo() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

req $ANA POST /login '{"nome": "Ana", "idade": 40}' > /dev/null
req $BIA POST /login '{"nome": "Bia", "idade": 12}' > /dev/null

NUCLEO=$(req $ANA POST /nucleos '{"nome": "Família Silva"}' | campo nucleoId)
req $BIA POST /nucleos/$NUCLEO/membros > /dev/null

TAREFA=$(req $ANA POST /tarefas '{"nome": "Lavar a louça", "pontos": 10, "idadeMinima": 10, "horarioLimite": "2099-01-01T18:00:00Z"}' | campo tarefaId)
req $BIA POST /tarefas/$TAREFA/escolher > /dev/null
req $BIA POST /tarefas/$TAREFA/concluir > /dev/null
req $BIA POST /aprovar "{\"tarefaId\": \"$TAREFA\", \"aprovado\": true}" > /dev/null
req $ANA POST /aprovar "{\"tarefaId\": \"$TAREFA\", \"aprovado\": true}" > /dev/null
req $ANA GET /placar > /dev/null
echo
