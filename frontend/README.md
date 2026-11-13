# Frontend QuemFaz

React + Vite. O `npm run build` gera arquivos estáticos em `dist/`, que o Pulumi envia para um bucket S3 privado servido pelo CloudFront.

## Como o domínio é dividido

| Caminho | Origem no CloudFront | Cache |
|---|---|---|
| `/api/*` | API Gateway → Lambdas | desligado |
| todo o resto | S3 (`dist/`) | `assets/*` imutável (nome com hash); `index.html` revalidado a cada acesso |

Como front e API ficam no mesmo domínio, não há CORS. Por causa do prefixo, o `demo.sh` na nuvem roda com `./demo.sh https://<url>/api`.

## Rodar localmente

Na raiz do repositório:

```bash
make install   # só na primeira vez: AWS CLI, SAM, Pulumi, uv e Node.js
make dev       # banco + API + frontend → http://localhost:5173 (Ctrl+C para parar)
make stop      # derruba o DynamoDB Local
```

O `make dev` confere antes se Docker, SAM e Node estão disponíveis e diz o que falta. O Vite repassa `/api/*` para o `sam local` (porta 3000). Os dados do DynamoDB Local ficam só em memória: somem quando o container para.

Para apontar para outra API: `API_URL=https://<url>/api npm run dev`.

## Deploy

O programa Pulumi faz o build do front sozinho (`npm install` + `npm run build`) antes de enviar o `dist/` ao S3. Então basta `make deploy` na raiz (ou `cd pulumi && pulumi up -s dev`).

## Autenticação

Enquanto o Cognito (#40) não está pronto, o email digitado no login vira o `x-membro-id`. A troca pelo token fica concentrada em `cabecalhoAuth` em [src/api.js](src/api.js).
