# Histórico de alterações

## Não publicado

### Adicionado

- Lista local ilustrativa de senhas conhecidas e comparação com variações
  triviais de caixa, acentos, sufixos e substituições de caracteres.
- Limitação por IP: 90 requisições em 60 segundos, Retry-After e HTTP 429,
  com contadores em memória e proteção de concorrência.
- Testes de concorrência, expiração de cota, entradas máximas, restauração
  pelo histórico e respostas JSON inválidas ou incompatíveis.
- Sete cenários Playwright para desktop e celular, ainda sem execução local.
- Benchmark sintético com 4096 caracteres e execução concorrente.
- requirements-prod.txt com Waitress para implantação WSGI opcional.
- Quatro testes HTTP para identidade FirePassJW, controles de senha,
  indicadores e rótulos acessíveis.
- Onze testes JavaScript com DOM e rede simulados para digitação, estados,
  requisições atrasadas, falhas, timeout, Unicode e limpeza da entrada.
- Interface web Flask com visual responsivo, barra de força, critérios,
  recomendações em tempo real e controles para mostrar e limpar a entrada.
- Modo --web no mesmo arquivo principal e rota POST /api/analisar.
- Limites HTTP, cabeçalhos de privacidade e restrição a hosts e origens locais.
- Quinze testes HTTP para página, recursos, análise, validação e privacidade.
- Testes de integração de verificador_senhas.py em subprocessos.
- Testes de tamanho máximo, representações Unicode equivalentes, frases
  longas e sequências maiúsculas e invertidas.
- Workflow do GitHub Actions para Python 3.10 e 3.14 em Windows, Linux e macOS.

### Alterado

- README detalha problema e solução, arquitetura e uso da IA: contribuição
  da ferramenta, decisões humanas, exemplos de prompts, riscos mitigados
  e validações ainda pendentes.
- Versões Python diretas e transitivas fixadas a partir do ambiente validado.
- Cores de texto e alertas com mais contraste, foco visível e controles maiores.
- Frontend valida o formato da resposta antes de atualizar os indicadores.
- Testes estáticos fecham as respostas HTTP para liberar os arquivos abertos.
- Workflow atualizado para executar os testes de comportamento JavaScript.
- Fontes dos quadros de análise e recomendações aumentadas em 2 px,
  com ajustes de quebra de linha para telas menores.
- Interface e favicon atualizados para uma paleta azul, incluindo fundos,
  foco, controles e indicadores de critérios e senhas fortes.
- Normalização Unicode NFC antes da avaliação estrutural.
- Sequências e repetições consecutivas limitam a nota quando cobrem pelo
  menos metade do texto, reduzindo falsos positivos em textos longos.
- Blocos integralmente repetidos continuam limitados a Fraca.
- Textos com oito caracteres distintos recebem nível mínimo Forte a partir
  de 20 caracteres avaliados e Muito forte a partir de 28, antes das penalizações.
- Formatação dos testes e documentação de regras, limitações e validação.
- Removido o atalho main.py; verificador_senhas.py é o único executável.
- Testes movidos para tests/, com comandos da documentação e CI atualizados.
- Normalização e cálculo estrutural separados em funções internas menores.
- Testes de integração simplificados para o único executável do projeto.
- README revisado para explicar o problema resolvido, instalação, execução,
  testes, limitações e participação da IA no desenvolvimento.
- Critérios compartilhados entre o terminal e a interface web.
- CI atualizado para instalar Flask e conferir a sintaxe JavaScript.

### Estado do projeto

- Verificador local com entrada oculta, recomendações e códigos de saída.
- Flask adicionado para o modo web; o terminal continua sem dependências
  externas. A antiga API de saúde permanece removida.
- Flask instalado no ambiente: 49 testes Python e 15 testes JavaScript
  passaram, sem testes ignorados. Interface ainda sem validação visual em navegador.
- Nenhuma versão publicada, tag ou commit criado neste trabalho.
- Inicialização Git pendente porque o executável não está disponível.
- Matriz de compatibilidade configurada, ainda sem execução no GitHub.
- Playwright não instalado devido ao bloqueio do npm. Chrome headless falhou
  por restrições locais. Os 14 cenários previstos não foram executados.
- Instalação do Waitress também bloqueada; HTTPS depende do ambiente de publicação.
