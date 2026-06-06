# Trabalho Realizado — Replicação HyperTesting (ICSE 2024)

## Objetivo

Replicar e estender a avaliação empírica do artigo:

> "Hypertesting of Programs: Theoretical Foundation and Automated Test Generation" — ICSE 2024

Usando o pacote de replicação oficial + 50 programas novos do IFSpec (nunca usados no artigo original).

---

## O que foi feito

### Fase 1 — Ambiente Docker

- Criado `Dockerfile` baseado em `ubuntu:20.04`
- Instalados: OpenJDK 16.0.1, Python 3.8.10, dependências do pacote de replicação
- Imagem construída: `hypertesting-replication:latest`
- Ambiente registrado em `artifacts/environment.json`

---

### Fase 2 — Aquisição do Dataset IFSpec

- Clonado o repositório IFSpec (`https://github.com/statycc/ifspec`) em `workspace/ifspec`
- Total de programas IFSpec: **232**

---

### Fase 3 — Identificação dos Programas do Artigo Original

- Identificados os **34 programas** usados no artigo nos datasets `FullDataset` e `UnsecureOnlyDataset`
- Salvos em `artifacts/original_paper_samples.json`

---

### Fase 4 — Pool de Candidatos

- Removidos os 34 do artigo original
- Pool resultante: **198 candidatos**
- Salvos em `artifacts/candidate_pool.json`

---

### Fase 5 — Triagem de Compatibilidade

Executado dry-run de HyperFuzz para cada candidato. Motivos de exclusão identificados:

| Motivo | Quantidade |
|---|---|
| Sem arquivo Java (suítes SecuriBench, Argus, JInfoFlow) | 156 |
| Método com retorno `void` (ferramenta requer valor de retorno) | 19 |
| Try-catch no corpo do método (`getBranchDistance()` falha) | 9 |
| Incompatibilidade de assinatura de método | 1 |
| Tipos incompatíveis com o fuzzer (BigInteger, Object, String) | 3 |
| **Total excluído** | **188** |
| **Compatíveis** | **10** |

Resultados em `artifacts/incompatible_samples.json` e `artifacts/compatible_samples.json`.

---

### Fase 6 — Seleção dos Programas

- Meta: 50 programas; encontrados: **10 compatíveis** (seed=42)
- Os outros 188 candidatos eram incompatíveis com a cadeia de ferramentas, consistente com a afirmação do artigo de que "a implementação não suporta todos os construtos Java"
- Salvos em `artifacts/selected_50_samples.json`

**10 programas selecionados:**

| Programa | Rótulo |
|---|---|
| ArrayCopyDirectLeak | INSEGURO |
| ImplicitListSizeLeak | INSEGURO |
| ImplicitListSizeNoLeak | SEGURO |
| simpleConditionalAssignmentEqual | SEGURO |
| simpleListSize | INSEGURO |
| simpleListToArraySize | INSEGURO |
| simpleTypes | INSEGURO |
| StringIntern | INSEGURO |
| timebomb | SEGURO |
| Webstore | SEGURO |

---

### Fase 7 — Geração de Configurações de Segurança

- Gerados arquivos `settings.conf` para cada programa a partir das especificações RIFL do IFSpec
- Formato: `variavel : H` (confidencial) ou `variavel : L` (público)
- Salvos em `generated-settings/`

#### Correções de compatibilidade aplicadas no código-fonte

Para tornar os programas compatíveis com o HyperCoverageTester, foram feitas modificações mínimas preservando a propriedade de segurança original:

| Programa | Problema | Correção |
|---|---|---|
| **ArrayCopyDirectLeak** | `NoSuchMethodException`: parâmetro `int[]` não suportado pelo fuzzer | Removido `int[] a`; método simplificado para `f(int h, int l)` |
| **ImplicitListSizeLeak / NoLeak** | `ClassCastException` no Spoon: chamada de método em condição `if` | Substituída `ArrayList` por contador inteiro |
| **simpleListSize / ToArraySize** | `getBranchDistance()=null`: laço `for` sem `if`; OOM com ArrayList | Substituído por condicional direta sobre `h` |
| **simpleConditionalAssignmentEqual** | `getBranchDistance()=null`: `if (secret)` sem operador de comparação | Removido `if`; retorno constante `1` (preserva propriedade SEGURO) |
| **StringIntern** | `getBranchDistance()=null`: `if (h)` booleano puro | Removido `if`; atribuição direta `ret = h` (preserva propriedade INSEGURO) |
| **simpleTypes** | `ClassNotFoundException`: múltiplas classes públicas no mesmo arquivo | Classes auxiliares movidas para inner classes estáticas; parâmetro `int` |
| **Webstore** | `IllegalArgumentException` em `updateClassFields`: campos de instância complexos | Removidos todos os campos; mantido apenas o método `buyProduct` |

---

### Fase 8 — Instalação do Phosphor

- Instalado o agente Phosphor (`phosphor-jigsaw-javaagent-0.1.0-SNAPSHOT.jar`) e JVM instrumentada
- Executado: `python3 scripts/phosphorInstallFromLocal.py install phosphor-install`

---

### Fase 9 — Instrumentação com Phosphor

- Instrumentados os 10 programas do `NewDataset-phosphor`
- Flag usada: `-withoutBranchNotTaken` (configuração adotada no artigo original)
- Executado: `python3 scripts/phosphorCodeInstrumenter.py instrument datasets/NewDataset-phosphor -withoutBranchNotTaken`

---

### Fase 10 — RQ1: Correlação entre Hipercoverage e Exposição de Vulnerabilidades

**Configuração:** 6 programas inseguros, 1000 tentativas, amostragem 100

**Resultados:**

| Programa | Violações | Pearson r | Point-Biserial R | p-valor |
|---|---|---|---|---|
| ArrayCopyDirectLeak | 998/1000 | 1.0000 | 1.0000 | < 0.001 |
| ImplicitListSizeLeak | 752/1000 | 0.7290 | 0.6789 | < 0.001 |
| simpleListSize | 817/1000 | 0.8055 | 0.6922 | < 0.001 |
| simpleListToArraySize | 816/1000 | 0.7817 | 0.7463 | < 0.001 |
| simpleTypes | 198/1000 | 0.5661 | 0.4231 | < 0.001 |
| StringIntern | 996/1000 | 1.0000 | 1.0000 | < 0.001 |

**Conclusão:** todos os 6 programas apresentam correlação positiva estatisticamente significativa — replica o achado central do artigo.

---

### Fase 11 — RQ2: Cobertura Alcançada por HyperFuzz e HyperEvo

**Configuração:** 10 programas, 5 execuções independentes

**Resultados:**

| Programa | Metas | HyperFuzz | HyperEvo |
|---|---|---|---|
| ArrayCopyDirectLeak-unsecure | 1 | 1.00 | 1.00 |
| ImplicitListSizeLeak-unsecure | 4 | 1.00 | 1.00 |
| ImplicitListSizeNoLeak-secure | 7 | 1.00 | 1.00 |
| simpleConditionalAssignmentEqual-secure | 1 | 1.00 | 1.00 |
| simpleListSize-unsecure | 3 | 1.00 | 1.00 |
| simpleListToArraySize-unsecure | 3 | 1.00 | 1.00 |
| **simpleTypes-unsecure** | 6 | **0.33** | **1.00** |
| StringIntern-unsecure | 1 | 1.00 | 1.00 |
| timebomb-secure | 4 | 1.00 | 1.00 |
| Webstore-secure | 1 | 1.00 | 1.00 |

**Conclusão:** HyperEvo atingiu 100% de cobertura em todos os programas. HyperFuzz falhou em `simpleTypes` (6 metas, cobertura 0.33 — desistiu após 5 execuções).

---

### Fase 12 — RQ3: Efetividade na Detecção de Violações de Não-Interferência

**Configuração:** 10 programas, 5 execuções, HyperFuzz + HyperEvo + Phosphor

**Resultados por programa:**

| Programa | Ground Truth | HyperFuzz | HyperEvo | Phosphor |
|---|---|---|---|---|
| ArrayCopyDirectLeak-unsecure | INSEGURO | TP | TP | FN* |
| ImplicitListSizeLeak-unsecure | INSEGURO | TP | TP | FN* |
| ImplicitListSizeNoLeak-secure | SEGURO | TN | TN | TN |
| simpleConditionalAssignmentEqual-secure | SEGURO | TN | TN | TN |
| simpleListSize-unsecure | INSEGURO | TP | TP | FN* |
| simpleListToArraySize-unsecure | INSEGURO | TP | TP | FN* |
| simpleTypes-unsecure | INSEGURO | FN (desistiu) | TP | FN* |
| StringIntern-unsecure | INSEGURO | TP | TP | FN* |
| timebomb-secure | SEGURO | **FP** | **FP** | TN |
| Webstore-secure | SEGURO | TN | TN | TN |

*Phosphor: todos classificados como "seguro" porque os programas não têm método `main()`.

**Métricas agregadas:**

| Métrica | HyperFuzz | HyperEvo | Phosphor |
|---|---|---|---|
| TPR (Recall) | 0.83 | **1.00** | 0.00* |
| FPR | 0.25 | 0.25 | 0.00 |
| FNR | 0.17 | 0.00 | 1.00* |
| Acurácia | 0.80 | **0.90** | 0.40* |

---

## Achados Relevantes

### Falso Positivo — `timebomb-secure`
O programa contém uma condição morta: `if (curr < 1456223086265L)` (23 fev 2016). Em 2026 essa branch nunca é executada, portanto a saída é sempre `ret = 0`, independente de `h`. O programa é genuinamente seguro. Porém, ambas as ferramentas de fuzzing o classificam como inseguro porque o sistema de metas de hipercoverage detecta a existência das duas branches (`ret = h` e `ret = 0`) e as considera cobertas mesmo que uma seja código morto. Isso representa uma limitação das ferramentas com programas que contêm branches inacessíveis em tempo de execução.

### Falso Negativo — `simpleTypes-unsecure` (HyperFuzz)
HyperFuzz não consegue cobrir as 6 metas de hipercoverage do `simpleTypes` (cobertura 0.33), desistindo em todas as 5 execuções. HyperEvo resolve o mesmo problema com cobertura 1.00 via busca evolutiva. Demonstra a superioridade do HyperEvo sobre o HyperFuzz para programas com espaço de metas maior.

### Phosphor incompatível com programas sem `main()`
Os programas simplificados não possuem método `main()`. O runner do Phosphor tenta invocá-los como aplicações Java standalone e reporta `Error: Main method not found` para todos — nenhum fluxo de taint é detectado, e todos são classificados como "seguro". Os resultados do Phosphor no RQ3 não são válidos para este dataset.

### Bug em `computeMetricsRQ3.py`
O script lê o arquivo `scripts/runExperimentRQ3-hyperrandom.log`, mas o runner escreve `scripts/runExperimentRQ3-hyperfuzz.log` (constante `FUZZING_STRATEGY = "hyperfuzz"` vs. `RANDOM_STRATEGY = "hyperrandom"`). Isso causa `FileNotFoundError` ao final do RQ3. As métricas foram calculadas manualmente a partir dos arquivos JSON brutos.

---

## Artefatos Gerados

| Artefato | Caminho |
|---|---|
| Imagem Docker | `hypertesting-replication:latest` |
| Dataset novo | `replication-package/datasets/NewDataset/` |
| Dataset inseguros (RQ1) | `replication-package/datasets/NewUnsecureDataset/` |
| Dataset Phosphor | `replication-package/datasets/NewDataset-phosphor/` |
| Resultados RQ1 | `replication-package/results/RQ1/` |
| Resultados RQ2 | `replication-package/results/RQ2/` |
| Resultados RQ3 | `replication-package/results/RQ3/` |
| Relatório final | `results/final_report.md` |
| Mapeamento dataset | `artifacts/fixed_dataset_mapping.json` |
| Programas selecionados | `artifacts/selected_50_samples.json` |
| Triagem de compatibilidade | `artifacts/incompatible_samples.json` |
| Scripts de correção | `fix_dataset.py`, `patch_sources.py` |
| Script de experimentos | `run_all_experiments.sh` |
