# Instruções para agentes de IA (Claude Code, Cursor, etc.)

Este projeto analisa testes A/B de cashback do Méliuz. Quando o usuário pedir
para analisar um teste, siga este fluxo:

## 1. Identifique o arquivo do teste e o objetivo
Se o usuário não informou o caminho do CSV, pergunte. O schema esperado é:
`Data, Grupos de usuários, Parceiro, compradores, comissão, cashback, vendas totais`.

Além do arquivo, verifique se o objetivo do teste está claro. Growth raramente
otimiza uma métrica só — às vezes o objetivo é lucro, às vezes eficiência de
capital (ROI), às vezes aquisição (volume de compradores). Se o usuário não
disser qual é o objetivo, **pergunte antes de rodar**, por exemplo:

> "Você quer priorizar lucro líquido, ROI (eficiência de capital), ou volume
> de compradores (aquisição) como critério pra escolher o vencedor?"

Se o usuário responder algo ambíguo ou pedir "o padrão", use lucro líquido
(é o default do `config.yaml`) e diga isso explicitamente na resposta.

## 2. Rode o pipeline
```bash
python main.py <caminho_do_csv> --nome "<nome descritivo do teste>" --metrica-alvo <lucro|roi|compradores>
```
Não escreva um script novo para cada teste — este `main.py` já é genérico e
funciona para qualquer CSV nesse schema, com qualquer número de grupos/parceiro,
e para qualquer uma das 3 métricas-alvo, sem mudar código.
Se quiser controlar a pasta de saída: `--output-dir output/<algo>`.

Se o usuário pedir pra reavaliar com um alpha diferente, ou trocar a
métrica-alvo depois de ver o primeiro resultado, rode de novo com os novos
parâmetros — não precisa editar nada em `src/`, só o argumento do comando.

## 3. Leia o resultado
O comando gera, dentro de `output/<nome_do_arquivo>/`:
- `analysis.json` — todos os números, testes estatísticos e a decisão, estruturados
- `relatorio.md` — relatório executivo já pronto, com gráficos
- `profit_bar.png`, `daily_trend.png` — gráficos usados no relatório

Leia o `analysis.json` (não precisa reprocessar o CSV) para responder o usuário.

## 4. Explique em linguagem executiva — e vá além do template
Use `analysis["decisao"]["resumo"]` como base, e traga as 3 dimensões da
decisão (`analysis["decisao"]["dimensoes"]`: confiança, impacto financeiro,
risco) — não repita só a palavra "ESCALAR" ou "NÃO ESCALAR" sem contexto.

Depois, olhe `analysis["insights_automaticos"]`: são padrões factuais
detectados no dado (ex: "grupo X tem mais compradores mas menos lucro que Y").
Não leia essa lista pro usuário ao pé da letra — **raciocine em cima dela**,
como um analista sênior faria, conectando o padrão a uma hipótese de negócio
plausível. Por exemplo, se o insight diz que um grupo tem mais compradores
mas menos lucro, você pode dizer algo como: "isso pode indicar que o
incentivo de cashback nesse grupo está acima do ponto ótimo — está trazendo
volume, mas o custo extra está corroendo a margem." A regra de ouro: toda
interpretação sua tem que estar ancorada em um número que já está no JSON —
nunca invente uma cifra ou percentual novo, só interprete os que existem.

Traga também `analysis["decisao"]["justificativa_metrica"]` — explique por
que a métrica escolhida (ou o padrão) faz sentido pra essa decisão específica.

Nunca esconda avisos de qualidade de dado do usuário — eles fazem parte da
recomendação, não são um detalhe técnico, e estão em
`analysis["avisos_qualidade_dados"]`.

Nunca decida "no olho" por cima do pipeline. A decisão em `analysis["decisao"]`
já combina significância estatística + efeito de negócio + qualidade dos
dados — não a substitua por uma leitura superficial do CSV. Sua interpretação
qualitativa (item acima) complementa a decisão, não a substitui.

## 5. Planilha de acompanhamento
O pipeline já registra automaticamente o teste (linha nova) na planilha de
acompanhamento — Google Sheets se houver `service_account.json` + variável de
ambiente `AB_TEST_SHEET_ID` configurados, ou `output/tracking_sheet.csv` como
fallback. Informe ao usuário onde o registro foi salvo
(`analysis["registro_planilha"]`).

## Regras gerais
- Não hardcode nomes de grupo, parceiro ou número de variantes em nenhum lugar.
- Se o usuário pedir para comparar múltiplos testes já rodados, leia os
  `analysis.json` de cada pasta em `output/` em vez de reprocessar os CSVs.
- Se o CSV tiver colunas com nomes ligeiramente diferentes (ex: "Buyers" em
  vez de "compradores"), o `data_loader.py` já tenta casar por aliases — não
  é necessário editar código para isso.
