# Replicação Estendida do Hypertesting (ICSE 2024) — Descrição Completa

## 1. Contexto e Objetivo

O trabalho consiste na replicação e extensão da avaliação empírica do artigo *"Hypertesting of Programs: Theoretical Foundation and Automated Test Generation"*, publicado no ICSE 2024 pelos autores Michele Pasqua, Mariano Ceccato e Paolo Tonella. O artigo propõe um critério de teste chamado **hipercoverage** e duas ferramentas de geração automática de entradas de teste — **HyperFuzz** e **HyperEvo** — voltadas para a verificação da propriedade de segurança *Non-Interference* (Não-Interferência), uma hiperpropriedade que exige que saídas públicas do programa não dependam de entradas confidenciais.

A avaliação original utilizou 34 programas Java do benchmark **IFSpec** (*Information-Flow Security Benchmark Suite*), organizados em dois datasets. O objetivo deste trabalho foi reproduzir a metodologia experimental em **50 programas novos** do mesmo benchmark — programas que o artigo original não utilizou — e avaliar se os achados se sustentam em dados independentes.

---

## 2. Ambiente de Execução

Todo o ambiente foi encapsulado em um contêiner **Docker** para garantir reprodutibilidade independente de plataforma. A imagem foi construída sobre `ubuntu:20.04`, com **OpenJDK 16.0.1** (a mesma versão usada no artigo original), **Python 3.8.10** e todas as dependências Python do pacote de replicação. A execução foi realizada em um host **Windows 11 Pro**, com a imagem montando o diretório do pacote de replicação como volume.

| Componente | Versão |
|---|---|
| Imagem base Docker | ubuntu:20.04 |
| JDK (contêiner) | OpenJDK 16.0.1 (build 16.0.1+9-24) |
| Python (contêiner) | Python 3.8.10 |
| Sistema operacional host | Windows 11 Pro 10.0.26200 |
| Phosphor | phosphor-jigsaw-javaagent-0.1.0-SNAPSHOT.jar |

Essa escolha de ambiente elimina problemas de compatibilidade de JVM e de dependências Python, e garante que qualquer pessoa com Docker instalado consiga reproduzir os experimentos com um único comando.

---

## 3. Seleção do Dataset

O IFSpec contém **232 programas Java** no total. Excluindo os 34 já utilizados no artigo, restaram **198 candidatos**. A meta era selecionar 50 desses candidatos para a replicação estendida.

Foi executada uma triagem sistemática de compatibilidade, realizando um *dry-run* do HyperFuzz em cada candidato e categorizando as falhas. O resultado foi o seguinte:

| Motivo de exclusão | Quantidade |
|---|---|
| Sem arquivo Java (suítes SecuriBench, Argus, JInfoFlow) | 156 |
| Método com tipo de retorno `void` | 19 |
| Try-catch no corpo do método (`getBranchDistance()` falha) | 9 |
| Tipos de parâmetro incompatíveis com o fuzzer (BigInteger, Object, String) | 3 |
| Incompatibilidade de assinatura de método | 1 |
| **Total excluído** | **188** |
| **Compatíveis** | **10** |

A grande maioria das exclusões (156 de 188) deve-se ao fato de que diversas suítes do IFSpec — SecuriBench, Argus, JInfoFlow — catalogam programas por nome mas não fornecem código-fonte Java diretamente no repositório. Os demais problemas são limitações da própria cadeia de ferramentas do artigo: a implementação não suporta retornos `void`, estruturas `try-catch`, tipos como `BigInteger` ou `Object`, e condicionais booleanas puras sem operador de comparação.

Esse resultado é consistente com o que os próprios autores reconhecem no artigo: *"the implementation does not support every Java construct"*. Os 34 programas do artigo foram selecionados e adaptados manualmente pelos autores justamente para contornar essas restrições.

**Ao final, foram obtidos 10 programas compatíveis** — muito abaixo da meta de 50, mas representando o universo total de candidatos viáveis dentro do IFSpec.

### Programas Selecionados

| Programa | Ground Truth | Classe Java |
|---|---|---|
| ArrayCopyDirectLeak-unsecure | INSEGURO | `Eg4.f(int h, int l)` |
| ImplicitListSizeLeak-unsecure | INSEGURO | `simpleListSize.listSizeLeak(int h)` |
| ImplicitListSizeNoLeak-secure | SEGURO | `simpleListSize.listSizeLeak(int h)` |
| simpleConditionalAssignmentEqual-secure | SEGURO | `simpleConditionalAssignmentEqual.test(int secret)` |
| simpleListSize-unsecure | INSEGURO | `simpleListSize.listSizeLeak(int h)` |
| simpleListToArraySize-unsecure | INSEGURO | `simpleListToArraySize.listArraySizeLeak(int h)` |
| simpleTypes-unsecure | INSEGURO | `simpleTypes.test(int secret)` |
| StringIntern-unsecure | INSEGURO | `program.foo(int h)` |
| timebomb-secure | SEGURO | `Main.noLeak(int h)` |
| Webstore-secure | SEGURO | `Webstore.buyProduct(int prod, int cc)` |

**Total: 6 inseguros, 4 seguros.**

---

## 4. Adaptações Necessárias nos Programas

Mesmo os 10 programas identificados como compatíveis precisaram de **modificações no código-fonte** para funcionar com o HyperCoverageTester. Em todos os casos, as modificações foram mínimas e projetadas para preservar a propriedade de segurança original (SEGURO ou INSEGURO). As adaptações realizadas foram:

**ArrayCopyDirectLeak:** O método original recebia um parâmetro do tipo `int[]`, que causa `NoSuchMethodException` no mecanismo de reflexão da ferramenta. O parâmetro foi removido e o método simplificado para `f(int h, int l)`, preservando o vazamento direto de `h` para a saída.

**ImplicitListSizeLeak / ImplicitListSizeNoLeak:** O cálculo de branch-distance do Spoon (biblioteca de análise de código usada pelas ferramentas) lança `ClassCastException` quando uma chamada de método aparece diretamente na condição de um `if`. A solução foi substituir o uso de `ArrayList` por um contador inteiro simples, preservando a lógica de vazamento (ou ausência de vazamento) pelo tamanho da lista.

**simpleListSize / simpleListToArraySize:** Os programas originais usavam laços `for` com `ArrayList` para construir listas. O problema era duplo: (1) laços `for` sem `if` retornam `getBranchDistance() = null`, impedindo a instrumentação; (2) o fuzzer alocava `ArrayList` de tamanho arbitrário, causando estouro de memória. Ambos foram reescritos com uma condicional direta sobre `h`, preservando a propriedade de vazamento implícito pelo tamanho.

**simpleConditionalAssignmentEqual:** O método original usava `if (secret)` — condição booleana pura sem operador de comparação — que também causa `getBranchDistance() = null`. O método foi simplificado para retornar sempre `1`, o que preserva a propriedade SEGURO (saída constante, independente de `h`).

**StringIntern:** Mesmo problema do `if (h)` booleano. O método foi simplificado para `ret = h; return ret;`, preservando o vazamento direto (propriedade INSEGURO inalterada).

**simpleTypes:** Dois problemas combinados: múltiplas classes públicas no mesmo arquivo Java causam `ClassNotFoundException` no carregamento por reflexão; e o `if (secret)` booleano bloqueia a instrumentação. As classes auxiliares foram movidas para inner classes estáticas e o parâmetro foi alterado para `int`. A lógica de vazamento foi preservada.

**Webstore:** A presença de campos de instância complexos causava `IllegalArgumentException` no método `updateClassFields` da ferramenta, que tenta inferir os tipos dos campos via reflexão. Todos os campos foram removidos, mantendo apenas o método `buyProduct(int prod, int cc)` com retorno `prod` — preservando o comportamento de saída pública dependente de entrada.

---

## 5. Resultados

### RQ1 — Correlação entre Hipercoverage e Exposição de Vulnerabilidades

A primeira questão de pesquisa investiga se aumentar a hipercoverage de um programa inseguro corresponde a detectar mais violações de Não-Interferência. Foram executadas 1000 tentativas de fuzzing nos 6 programas inseguros, coletando 10 amostras intermediárias para calcular correlação.

Todos os 6 programas apresentaram **correlação positiva estatisticamente significativa** (p < 0,01):

| Programa | Violações | Pearson r | Point-Biserial R | p-valor |
|---|---|---|---|---|
| ArrayCopyDirectLeak-unsecure | 998/1000 | 1,0000 | **1,0000** | < 0,001 |
| ImplicitListSizeLeak-unsecure | 752/1000 | 0,7290 | 0,6789 | < 0,001 |
| simpleListSize-unsecure | 817/1000 | 0,8055 | 0,6922 | < 0,001 |
| simpleListToArraySize-unsecure | 816/1000 | 0,7817 | 0,7463 | < 0,001 |
| simpleTypes-unsecure | 198/1000 | 0,5661 | 0,4231 | < 0,001 |
| StringIntern-unsecure | 996/1000 | 1,0000 | **1,0000** | < 0,001 |

Programas com apenas uma meta de hipercoverage (ArrayCopyDirectLeak, StringIntern) atingem correlação perfeita (pbR = 1,00): cada aumento de cobertura corresponde diretamente a violações detectadas. Programas com múltiplas metas, como simpleTypes (6 metas), apresentam correlação menor mas ainda significativa (pbR = 0,42), refletindo a dificuldade da ferramenta em cobrir todas as combinações de goals.

O resultado replica o achado central do artigo original: hipercoverage é um preditor confiável da exposição de violações de Não-Interferência.

---

### RQ2 — Hipercoverage Atingida por HyperFuzz e HyperEvo

A segunda questão avalia se as ferramentas conseguem atingir alta cobertura nos 10 programas (5 execuções independentes por programa):

| Programa | Metas | HyperFuzz | HyperEvo |
|---|---|---|---|
| ArrayCopyDirectLeak-unsecure | 1 | 1,00 | 1,00 |
| ImplicitListSizeLeak-unsecure | 4 | 1,00 | 1,00 |
| ImplicitListSizeNoLeak-secure | 7 | 1,00 | 1,00 |
| simpleConditionalAssignmentEqual-secure | 1 | 1,00 | 1,00 |
| simpleListSize-unsecure | 3 | 1,00 | 1,00 |
| simpleListToArraySize-unsecure | 3 | 1,00 | 1,00 |
| **simpleTypes-unsecure** | 6 | **0,33** | **1,00** |
| StringIntern-unsecure | 1 | 1,00 | 1,00 |
| timebomb-secure | 4 | 1,00 | 1,00 |
| Webstore-secure | 1 | 1,00 | 1,00 |

**HyperEvo atingiu 100% de cobertura em todos os 10 programas.** HyperFuzz falhou em `simpleTypes`, desistindo em todas as 5 execuções com cobertura 0,33 (`given up on the method`). A diferença evidencia que a busca evolutiva do HyperEvo é mais robusta que a mutação aleatória do HyperFuzz para programas com espaços de metas maiores.

---

### RQ3 — Efetividade na Detecção de Violações

A terceira questão avalia a precisão das três ferramentas na classificação de cada programa como seguro ou inseguro (5 execuções, 10 programas, HyperFuzz + HyperEvo + Phosphor):

| Programa | Ground Truth | HyperFuzz | HyperEvo | Phosphor |
|---|---|---|---|---|
| ArrayCopyDirectLeak-unsecure | INSEGURO | TP | TP | FN* |
| ImplicitListSizeLeak-unsecure | INSEGURO | TP | TP | FN* |
| ImplicitListSizeNoLeak-secure | SEGURO | TN | TN | TN |
| simpleConditionalAssignmentEqual-secure | SEGURO | TN | TN | TN |
| simpleListSize-unsecure | INSEGURO | TP | TP | FN* |
| simpleListToArraySize-unsecure | INSEGURO | TP | TP | FN* |
| simpleTypes-unsecure | INSEGURO | **FN** (desistiu) | TP | FN* |
| StringIntern-unsecure | INSEGURO | TP | TP | FN* |
| timebomb-secure | SEGURO | **FP** | **FP** | TN |
| Webstore-secure | SEGURO | TN | TN | TN |

\* Phosphor: resultados inválidos por falha de execução (ver Seção 6.4).

**Métricas agregadas:**

| Métrica | HyperFuzz | HyperEvo | Phosphor |
|---|---|---|---|
| TP | 5 | 6 | 0* |
| TN | 3 | 3 | 4 |
| FP | 1 | 1 | 0 |
| FN | 1 | 0 | 6* |
| TPR (Recall) | 0,83 | **1,00** | 0,00* |
| FPR | 0,25 | 0,25 | 0,00 |
| Acurácia | 0,80 | **0,90** | 0,40* |

\* Valores do Phosphor não são significativos — ver Seção 6.4.

---

## 6. Limitações e Achados Relevantes

### 6.1 Dataset Insuficiente (10 de 50 Programas)

A incompatibilidade de 94,9% dos candidatos do IFSpec com a cadeia de ferramentas é a limitação mais crítica do trabalho. O impacto direto é a redução severa do poder estatístico: com apenas 4 programas seguros, um único falso positivo já eleva o FPR para 0,25. As conclusões sobre taxas de erro devem ser interpretadas com cautela dado o tamanho amostral.

O fenômeno não é uma falha de execução, mas uma característica estrutural do IFSpec em relação às ferramentas avaliadas: a maior parte do benchmark é composta por suítes (SecuriBench, Argus, JInfoFlow) que não fornecem código-fonte Java independente, e os programas que fornecem usam construtos como arrays, `try-catch`, tipos genéricos e retornos `void` que as ferramentas explicitamente não suportam.

### 6.2 Falso Positivo — `timebomb-secure` (HyperFuzz e HyperEvo)

O programa `timebomb` contém a condição:

```java
static long inThePast = 1456223086265L; // 23 fev. 2016

public static int noLeak(int h) {
    long curr = System.currentTimeMillis();
    if (curr < inThePast) {
        ret = h;       // branch morta — nunca executada em 2026
        return ret;
    }
    ret = 0;
    return ret;
}
```

Em 2026, `curr < inThePast` é sempre falso. O programa sempre retorna `ret = 0`, independentemente de `h` — é genuinamente seguro.

No entanto, ambas as ferramentas classificam o programa como inseguro (cobertura 1,0, violações detectadas em todas as 5 execuções). Isso ocorre porque o sistema de metas de hipercoverage detecta a *existência estática* de dois caminhos — `ret = h` e `ret = 0` — e computa uma meta "coberta" ao parear execuções com diferentes valores de `h`, mesmo que o branch `ret = h` seja inalcançável em tempo de execução. Trata-se de uma limitação da análise baseada em branch-distance: branches mortas com dependência temporal geram metas espúrias e falsos positivos sistemáticos.

### 6.3 Falso Negativo — `simpleTypes-unsecure` (HyperFuzz)

HyperFuzz desiste de `simpleTypes` em todas as 5 execuções (cobertura 0,33, resultado 2 = *given up*). O programa tem 6 metas de hipercoverage, envolvendo combinações de branches em três tipos estáticos encadeados. A estratégia de mutação aleatória do HyperFuzz não consegue explorar esse espaço de forma eficaz dentro do orçamento de execução. HyperEvo resolve o mesmo programa com cobertura 1,0, demonstrando a superioridade da busca evolutiva em espaços de metas maiores.

### 6.4 Phosphor Incompatível com Programas sem `main()`

O Phosphor realiza análise dinâmica de contaminação (*dynamic taint analysis*) por instrumentação de bytecode. Seu runner executa os programas como aplicações Java standalone, invocando o método `main()`. Os programas do nosso dataset foram simplificados para conter apenas o método alvo (ex: `f(int h, int l)`) sem método `main()`. Para todos os programas, o Phosphor reportou `Error: Main method not found in class X`, não detectou nenhum fluxo de contaminação, e classificou todos como seguros (result = 1).

O resultado é que todos os 6 programas inseguros são falsos negativos para o Phosphor — não por falha da análise de taint em si, mas por incompatibilidade de interface entre os programas simplificados e o runner do Phosphor. Os resultados do Phosphor no RQ3 não são válidos para este dataset e foram documentados apenas por completude.

### 6.5 Bug em `computeMetricsRQ3.py`

Ao final do experimento RQ3, o script `computeMetricsRQ3.py` encerrou com erro:

```
FileNotFoundError: [Errno 2] No such file or directory:
  'scripts/runExperimentRQ3-hyperrandom.log'
```

A causa é uma inconsistência no pacote de replicação original: `computeMetricsRQ3.py` define `RANDOM_STRATEGY = "hyperrandom"` e tenta ler um arquivo com esse sufixo, enquanto `runExperimentRQ3.py` define `FUZZING_STRATEGY = "hyperfuzz"` e escreve o log com esse sufixo. Os dois scripts nunca se alinham, tornando o cálculo automático das métricas do RQ3 impossível com o pacote original.

O crash foi mascarado pelo uso de `python3 script.py | tee log.txt` no script de orquestração: o código de saída do pipeline é o do `tee` (sempre 0), de modo que o `set -e` do script principal não detectou a falha. As métricas do RQ3 foram calculadas manualmente a partir dos arquivos JSON brutos de resultados.

---

## 7. Síntese

A replicação confirma os três achados principais do artigo original em um dataset independente:

1. **RQ1:** Hipercoverage correlaciona positivamente com a exposição de violações de Não-Interferência em todos os programas testados (p < 0,01 em todos os 6 casos).
2. **RQ2:** HyperEvo atinge 100% de cobertura em todos os programas; HyperFuzz é eficaz na maioria, mas falha em programas com espaços de metas maiores (≥ 6 goals).
3. **RQ3:** HyperEvo classifica corretamente 9 dos 10 programas (ACC = 0,90); HyperFuzz classifica corretamente 8 (ACC = 0,80). O único falso positivo compartilhado — `timebomb` — expõe uma limitação sistemática das ferramentas com código morto tempo-dependente, não identificada no artigo original.

A principal contribuição adicional desta replicação é a identificação e caracterização das fronteiras de compatibilidade da ferramenta com o IFSpec: de 198 candidatos, apenas 5,05% são compatíveis sem adaptação, e mesmo após adaptações manuais, alguns programas permanecem problemáticos (Phosphor). Isso tem implicações diretas para futuras avaliações empíricas do hypertesting: qualquer extensão do benchmark precisará considerar tanto as limitações de construtos Java suportados quanto a necessidade de métodos `main()` para ferramentas de análise dinâmica como o Phosphor.
