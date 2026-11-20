# Frontend QuemFaz

React + Vite. O `npm run build` gera arquivos estáticos em `dist/`, que o Pulumi envia para um bucket S3 privado servido pelo CloudFront.

## Como o domínio é dividido

| Caminho | Origem no CloudFront | Cache |
|---|---|---|
| `/api/*` | API Gateway → Lambdas | desligado |
| todo o resto | S3 (`dist/`) | `assets/*` imutável (nome com hash); `index.html` revalidado a cada acesso |

Como front e API ficam no mesmo domínio, não há CORS.

## Localmente

No `make dev`, o Vite faz o papel do CloudFront: repassa `/api/*` para o `sam local` (porta 3000).

## Deploy

O Pulumi faz o build do front (`npm install` + `npm run build`) e envia o `dist/` ao S3 a cada deploy. Com o CD, isso acontece sozinho depois de cada merge no `main`.

## Autenticação

No site, o login é com a conta Google, pelo Cognito ([src/auth.js](src/auth.js)), e cada requisição à API leva o token. Localmente, sem Cognito, o email digitado no login identifica a pessoa (header `x-membro-id`).
