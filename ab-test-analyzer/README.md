# Analisador de Testes A/B de Cashback — Méliuz

Solução reutilizável que recebe o CSV de um teste A/B de cashback e devolve
uma análise estatística completa + uma decisão acionável ("qual variante
escalar pra 100% do tráfego?"), sem precisar tocar em código entre um teste
e outro.

## Como usar (linguagem natural, via agente de IA)

Abra o projeto no Claude Code, Cursor, ou outra ferramenta de IA com acesso a
terminal, e peça em linguagem natural:

> "Analisa o teste do parceiro B, arquivo `data/dataset_02_parceiroB.csv`"

O agente vai ler o [`CLAUDE.md`](./CLAUDE.md) deste repositório, que instrui
exatamente como rodar o pipeline, onde ler o resultado e como explicar pro
usuário. Isso é o que faz a "ferramenta de IA" do enunciado funcionar sem
nenhuma integração de API paga — o agente já sabe operar o projeto sozinho.

## Como usar (linha de comando, direto)

```bash
pip install -r requirements.txt
python main.py data/dataset_01_parceiroA.csv --nome "Cashback Parceiro A - Q1 2011"
```

Funciona exatamente igual para qualquer um dos 3 datasets — e para qualquer
CSV novo no mesmo schema — sem alterar uma linha de código:

```bash
python main.py data/dataset_02_parceiroB.csv
python main.py data/dataset_03_parceiroC.csv
python main.py /caminho/para/qualquer_teste_novo.csv --nome "Meu novo teste"
```

### Escolhendo o objetivo do teste (métrica-alvo)

"Qual variante escalar" depende do que o time quer maximizar. Por padrão a
solução otimiza **lucro líquido**, mas isso é configurável, sem mudar código:

```bash
python main.py data/dataset_02_parceiroB.csv --metrica-alvo lucro         # padrão
python main.py data/dataset_02_parceiroB.csv --metrica-alvo roi           # eficiência de capital
python main.py data/dataset_02_parceiroB.csv --metrica-alvo compradores   # aquisição/volume
```

Quando um agente de IA roda isso por você (ver seção abaixo), ele pergunta
qual objetivo você quer antes de escolher — não assume lucro por padrão sem
avisar.

Saída, dentro de `output/<nome_do_arquivo>/`:
- `relatorio.md` — relatório executivo (o que um gestor vai ler)
- `analysis.json` — todos os números e a decisão, em formato estruturado
- `profit_bar.png`, `daily_trend.png` — gráficos usados no relatório

Além disso, cada execução registra uma linha em uma planilha de
acompanhamento (ver seção Google Sheets abaixo).

## Relatórios já gerados (os 3 datasets do desafio)

- [`output/dataset_01_parceiroA/relatorio.md`](./output/dataset_01_parceiroA/relatorio.md)
- [`output/dataset_02_parceiroB/relatorio.md`](./output/dataset_02_parceiroB/relatorio.md)
- [`output/dataset_03_parceiroC/relatorio.md`](./output/dataset_03_parceiroC/relatorio.md)

## Planilha de acompanhamento

**Link (leitura pública):** `<COLOCAR_LINK_DO_GOOGLE_SHEETS_AQUI>`

Por padrão, sem nenhuma credencial configurada, o pipeline já grava em
`output/tracking_sheet.csv` (o "mínimo aceito" do desafio) — isso funciona
imediatamente, sem setup nenhum.

### Para gravar direto no Google Sheets (diferencial)
1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/),
   ative a API do Google Sheets, e crie uma **service account**.
2. Baixe a chave JSON da service account e salve como `service_account.json`
   na raiz do projeto (já está no `.gitignore`, não sobe pro GitHub).
3. Crie uma planilha no Google Sheets, compartilhe com o e-mail da service
   account (com permissão de editor), e compartilhe também publicamente com
   "qualquer pessoa com o link pode visualizar".
4. Pegue o ID da planilha (a parte da URL entre `/d/` e `/edit`) e exporte:
   ```bash
   export AB_TEST_SHEET_ID="<ID_DA_PLANILHA>"
   ```
5. Rode o pipeline normalmente — ele detecta as credenciais e passa a
   escrever direto na aba `Testes A/B - Growth` da planilha. Se qualquer
   coisa falhar (rede, permissão), ele cai automaticamente para o CSV local
   sem quebrar a execução.

## Arquitetura

```
                         Pessoa do time de Growth
                                  │
                "Analisa o teste do parceiro X, arquivo Y.csv"
                                  │
                                  ▼
                   Agente de IA (Claude Code / Cursor)
                       lê CLAUDE.md → sabe o que rodar
                                  │
                                  ▼
                      python main.py <csv> [--nome ...]
                                  │
                                  ▼
        ┌──────────────────────────────────────────────────┐
        │  src/data_loader.py                               │
        │    → normaliza schema, parseia moeda BRL,         │
        │      remove/registra dado ruim (não trava)        │
        │  src/metrics.py                                    │
        │    → lucro, ROI, ticket médio, take rate por grupo │
        │  src/stats_tests.py                                │
        │    → escolhe teste certo pro shape dos dados       │
        │      (Shapiro → paramétrico ou não-paramétrico)    │
        │      + comparações par-a-par com Bonferroni        │
        │  src/decision.py                                   │
        │    → combina estatística + efeito de negócio +     │
        │      qualidade de dado numa recomendação            │
        │  src/report.py + src/charts.py                     │
        │    → relatorio.md + gráficos, prontos sozinhos      │
        │  src/sheets_writer.py                               │
        │    → registra na planilha (Sheets ou CSV fallback)  │
        └──────────────────────────────────────────────────┘
                                  │
                                  ▼
              analysis.json + relatorio.md + planilha atualizada
                                  │
                                  ▼
                 Agente de IA lê o JSON e conversa com a pessoa
```

**Por que o relatório não depende de uma chamada de IA em tempo real:**
o `relatorio.md` é gerado inteiramente pelo Python a partir do
`analysis.json`. Isso torna o pipeline determinístico, testável e
reproduzível — rodar duas vezes com o mesmo CSV dá o mesmo relatório. O
agente de IA entra pra dar a experiência de "conversar em linguagem
natural" e humanizar a explicação, mas o artefato de entrega (o que vai pro
gestor) não depende de nenhuma API externa nem pode "alucinar" um número.

## Decisões de análise que valem explicar

- **A "métrica-alvo" é um parâmetro, não uma conta fixa.** Growth raramente
  otimiza uma única métrica — lucro absoluto, ROI (eficiência de capital) e
  volume de compradores (aquisição) respondem perguntas de negócio
  diferentes. A solução aceita as 3 via `--metrica-alvo`, e um agente de IA
  pergunta qual delas usar quando o objetivo não está claro (ver `CLAUDE.md`).
- **A decisão é reportada em 3 dimensões, não uma palavra só.** Confiança
  (o quanto a estatística sustenta o resultado), impacto financeiro (o
  tamanho prático do efeito) e risco (qualidade do dado por trás) são
  calculados separadamente e podem divergir de propósito — por exemplo, o
  Parceiro A tem um efeito observado grande (impacto "Alto") mas não é
  estatisticamente significativo (confiança "Baixa", risco "Alto"): a
  diferença parece grande na amostra, mas a variação dia a dia é alta
  demais pra confiar nela. É exatamente esse tipo de nuance que uma
  recomendação binária ESCALAR/NÃO ESCALAR esconderia.
- **Insights automáticos como base para a IA raciocinar, não pra decidir
  sozinha.** O pipeline detecta padrões factuais (`src/insights.py`) — ex:
  "o grupo com mais compradores não é o mais lucrativo", ou "um grupo opera
  com ROI abaixo de 1" — e os expõe em `analysis["insights_automaticos"]`.
  O agente de IA usa esses fatos como âncora pra uma leitura crítica em
  linguagem natural (ver `CLAUDE.md`), mas nunca inventa um número que não
  esteja no JSON.
- **Unidade de análise é o dia, não o usuário.** Os datasets só têm
  agregados diários por grupo — não há dado por usuário. Isso é dito
  explicitamente em todo relatório gerado (seção "Limitações conhecidas"),
  porque muda o que dá pra afirmar estatisticamente (o "n" é o número de
  dias observados, não o número de compradores).
- **Não existe taxa de conversão nesses dados** — não há visitantes/sessões,
  só compradores. A solução não inventa essa métrica.
- **O teste estatístico é escolhido, não fixo.** Cada grupo passa por
  Shapiro-Wilk (normalidade); se todos os grupos são compatíveis com
  distribuição normal e as variâncias são homogêneas (Levene), usa-se
  ANOVA/Welch t-test. Caso contrário, Kruskal-Wallis/Mann-Whitney U. Isso
  evita aplicar um teste paramétrico em dados que não sustentam essa
  suposição — mas essa metodologia fica compactada no fim do relatório
  (dentro de um `<details>` recolhível), porque um gestor de Growth quer ver
  a decisão primeiro, não a estatística.
- **Robustez a dado ruim:** linhas com data inválida, valor monetário
  ilegível, valores negativos ou duplicatas são tratadas (removidas ou
  agregadas) e cada ocorrência vira um aviso rastreável no relatório — o
  pipeline nunca falha silenciosamente nem finge que o dado está limpo.

## Estrutura do repositório

```
main.py                  # CLI — ponto de entrada único
config.yaml              # todos os thresholds/parâmetros (nada hardcoded)
CLAUDE.md                # instruções pro agente de IA operar o projeto
src/
  parsers.py             # parser robusto de moeda BRL
  data_loader.py          # schema + validação + qualidade de dado
  metrics.py              # métricas de negócio por grupo + opções de métrica-alvo
  stats_tests.py          # seleção e execução dos testes estatísticos
  decision.py              # motor de decisão (confiança/impacto/risco)
  insights.py               # padrões factuais automáticos p/ a IA interpretar
  charts.py                  # gráficos do relatório
  report.py                   # gerador do relatório Markdown
  sheets_writer.py              # Google Sheets + fallback CSV
data/                     # os 3 datasets do desafio
output/                   # relatórios, JSONs e gráficos gerados
```
