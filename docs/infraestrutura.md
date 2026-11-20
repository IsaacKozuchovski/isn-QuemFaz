# Infraestrutura e deploy

Toda a infraestrutura do QuemFaz na AWS é criada pelo Pulumi ([pulumi/__main__.py](../pulumi/__main__.py)).

## CI/CD (GitHub Actions)

- **CI** ([ci.yml](../.github/workflows/ci.yml)): a cada PR e push no `main`, roda os testes unitários e de integração e o build do frontend.
- **CD** ([cd.yml](../.github/workflows/cd.yml)): depois que o CI passa no `main`, faz o deploy do `dev` sozinho. O `prod` é manual: **Actions → CD → Run workflow → stack: prod**.

## Login

O login é feito com a conta Google, pelo Cognito.

## Sorteio e emails

A cada 5 minutos, o sistema sorteia as tarefas que ninguém escolheu até o horário-limite (UC06) e avisa o sorteado por email, enviado por `nao-responda@quemfaz.negoci.online` (configurado em `remetente` no stack).

O subdomínio é verificado no SES pelo próprio Pulumi (DKIM), e a conta já saiu do sandbox: os emails chegam para qualquer usuário cadastrado.

## Produção (subdomínio)

O stack `prod` publica o site em `quemfaz.negoci.online` (definido em `pulumi/Pulumi.prod.yaml`), com HTTPS. O subdomínio tem a própria zona DNS na nossa conta AWS:

1. `STACK=prod make deploy` cria a zona e mostra os servidores de nome (NS) no log. O deploy fica esperando a validação do certificado HTTPS: pode cancelar com Ctrl+C.
2. O dono de `negoci.online` cria um registro NS do subdomínio apontando para esses servidores.
3. `STACK=prod make deploy` de novo: o certificado é validado e o site sobe.

**Não destrua o stack `prod`.** Uma zona nova teria outros NS, e a delegação pararia de funcionar. Por isso a zona é protegida no Pulumi: um `pulumi destroy` no `prod` falha de propósito.

Depois do primeiro deploy, os NS também aparecem com `cd pulumi && pulumi stack output name_servers --stack prod`.
