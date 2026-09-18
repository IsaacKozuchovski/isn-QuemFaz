## Requisitos Funcionais (RF)

- **RF01**: O sistema deve ser uma aplicação cliente-servidor sobre plataforma Web.

- **RF02**: O sistema deve ter aplicação a ser executada no navegador do cliente, o frontend, cujo código deve ser descarregado sob demanda.

- **RF03**: O sistema deve ter aplicação na nuvem, o backend, para atender às requisições do frontend.

- **RF04**: O sistema deve ter documentação de API RESTful para comunicação entre frontend e backend.

- **RF05**: O sistema deve ter acesso controlado por esquema de autenticação e autorização via provedor externo Google.

- **RF06**: O sistema deve possuir persistência de dados de usuários em banco de dados.

- **RF07**: O sistema deve ter documentação de modelagem de dados e de arquitetura do sistema.

- **RF08**: O sistema deve ser capaz de enviar email e notificações para os usuários.

- **RF09**: O sistema deve registrar todas as operações críticas dos usuários no sistema para posterior análise.

- **RF10**: O sistema deve possuir cenários de desenvolvimento e de produção.

- **RF11**: O sistema deve ser implantado em nuvem, com o uso de IaC.

- **RF12**: O sistema deve ser implantado automaticamente em ambiente de produção com o uso de CI/CD.

- **RF13**: O sistema deve permitir criar um núcleo familiar e vincular múltiplos membros a ele.

- **RF14**: O sistema deve permitir o cadastro de tarefas domésticas com nome, pontuação, idade mínima e horário-limite.

- **RF15**: O sistema deve permitir que qualquer membro elegível (que atenda à restrição de idade da tarefa) escolha uma tarefa disponível para si.

- **RF16**: O sistema deve sortear automaticamente uma tarefa entre os membros elegíveis caso nenhum a escolha até o horário-limite definido.

- **RF17**: O sistema deve permitir que um membro marque uma tarefa como concluída, ficando pendente de aprovação.

- **RF18**: O sistema deve exigir a aprovação de outro membro da família (diferente de quem executou) para validar a conclusão e creditar os pontos.

- **RF19**: O sistema deve manter um placar de pontos acumulados por membro da família.

- **RF20**: O sistema deve permitir definir um horário-limite por tarefa no momento do cadastro.

## Requisitos Não Funcionais (RNF)

- **RNF01**: O sistema deve ter boa responsividade.

- **RNF02**: O sistema deve rodar com baixa latência.

- **RNF03**: O sistema deve rodar com custo mínimo de operação.

