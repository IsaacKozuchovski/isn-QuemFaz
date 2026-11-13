# Frontend QuemFaz

React + Vite. O `npm run build` gera arquivos estáticos em `dist/`, que o Pulumi envia para um bucket S3 privado servido pelo CloudFront.

## Como o domínio é dividido

| Caminho | Origem no CloudFront | Cache |
|---|---|---|
| `/api/*` | API Gateway → Lambdas | desligado |
| todo o resto | S3 (`dist/`) | `assets/*` imutável (nome com hash); `index.html` revalidado a cada acesso |

Como front e API ficam no mesmo domínio, não há CORS. Por causa do prefixo, o `demo.sh` na nuvem roda com `./demo.sh https://<url>/api`.

## Rodar localmente

Com o backend local no ar (`make dev` em `aws-sam/`):

```bash
npm ci
npm run dev       # http://localhost:5173 — /api/* é repassado para o sam local (porta 3000)
```

Para apontar para outra API: `API_URL=https://<url>/api npm run dev`.

## Deploy

Automático pelo GitHub Actions ([deploy.yml](../.github/workflows/deploy.yml)): build do front e `pulumi up` a cada push na `main`. Para fazer na mão:

```bash
cd frontend && npm ci && npm run build
cd ../pulumi && pulumi up -s dev
```

## Autenticação

Enquanto o Cognito (#40) não está pronto, o email digitado no login vira o `x-membro-id`. A troca pelo token fica concentrada em `cabecalhoAuth` em [src/api.js](src/api.js).
