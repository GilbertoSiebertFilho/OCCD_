# Sobreposição, leque e rampa no mapa de colheita: síntese dos testes A, B e C

29/10/2026. Os dados são os exports do SMS de 7 ensaios de 2026: Case IH (T19, T20, T25) e John Deere GreenStar 4 (T22, T23, T29, T30). O código é o do OCCD (`engine/clean/yield_clean.py`).

Cada teste congelou hipóteses, previsões e regra de decisão (com hash SHA-256) antes de calcular qualquer número. Depois, uma revisão adversarial refez as contas do zero. Onde o revisor corrigiu um número, uso o número corrigido.

Os intervalos são IC 95 % por bootstrap de passadas: a passada inteira é a unidade sorteada, nunca o registro isolado. 1 registro ≈ 1 s. "Exploratório" quer dizer análise feita depois de ver os resultados: serve para gerar hipótese, não para provar.

## Resposta curta

- **O leque de retângulos na curva não é sobreposição; é o jeito de desenhar.** Cada registro vira um retângulo W × D (largura × distância) puxado para trás ao longo do rumo. Numa curva, retângulos vizinhos se cruzam por dentro e deixam um vão do mesmo tamanho por fora. A faixa que a plataforma realmente varre entre dois registros não se sobrepõe à seguinte: 0 m² em 372.435 pares. Recorte de verdade numa curva só acontece com raio menor que meia plataforma (W/2). Isso atinge 0,002 a 0,020 % dos registros, e nenhum deles chega ao mapa final.
- **As faixas empilhadas no início da passada são em parte sobreposição real, e só na Case IH.** Nos primeiros 6 a 8 registros a plataforma passa sobre cabeceira colhida horas antes: 84 a 93 % da faixa do registro 1 já estava cortada. O F8 já remove esses registros. O resto do empilhamento é desenho: na Case IH a distância registrada (velocidade × duração) não bate com o passo do GPS, que chega em épocas de 0,2 s. Na John Deere não há sobreposição depois do registro 2.
- **A rampa de cor do vermelho para o verde não é sobreposição.**
  - Ela continua depois que a sobreposição acaba.
  - Na mesma cabeceira, o fim da passada é mais fundo que o início em 5 de 7 ensaios. Um efeito de borda do talhão não teria como saber para que lado a máquina ia, então a causa é a máquina: enchimento e esvaziamento do fluxo de grão e atraso do sensor.
  - O F7 atual (corta 4 registros no início e 2 no fim) é curto demais.
- **Calcular uma "largura efetiva" e corrigir a produtividade não se sustenta.**
  - A largura registrada está certa: o espaçamento medido entre passadas paralelas vizinhas é 0,992 a 0,9996 de W.
  - A correção y/(1 − f), em que f é a fração do registro já colhida, não deixa a curva plana. Na Case IH ela passa do ponto: 1,05 com 5 a 10 % de sobreposição e 1,11 com 10 a 15 %.
- **O que fazer, em resumo:**
  1. manter o F8 como remoção, não como correção;
  2. corrigir dois defeitos de geometria do F8 e refazer a dose-resposta;
  3. desenhar a faixa varrida no lugar do retângulo;
  4. testar o atraso de fluxo antes do F7 e do F8;
  5. só então medir o F7 por campo.

  A seção 4 traz cada item com o teste que o sustenta e o resultado que o refutaria.

## 1. O que a imagem mostra

No mapa parecem uma coisa só, mas são três fenômenos diferentes.

| No mapa | O que é | É sobreposição real? | Evidência |
|---|---|---|---|
| Leque de retângulos na curva | Artefato de desenho (detalhe abaixo) | Não. Exceção: raio < W/2, que são 0,002–0,020 % dos registros, nenhum no mapa final | Teste C: H1, H2, H3, H5 |
| Faixas empilhadas no início da passada | Case IH: parte desenho, parte cabeceira já colhida nos primeiros 6–8 registros. John Deere: só os registros 1–2 | Sim, nos primeiros 6–8 registros da Case IH | Teste C: H4, H6. Teste B: HO |
| Rampa vermelho → verde | Transiente da máquina (fluxo de grão, atraso do sensor), mais longo que o F7 | Não, depois que a sobreposição acaba | Teste B. Revisão B: R3 |

**Leque na curva.**
- Entre dois registros, a plataforma (largura W) varre um quadrilátero, limitado pela linha da barra no registro anterior e pela linha da barra no atual.
- Esses quadriláteros se encaixam sem sobra e sem buraco, desde que a curva seja aberta (raio ≥ W/2) e a máquina ande para a frente.
- O OCCD desenha outra coisa: um retângulo W × D (D = distância registrada) puxado para trás ao longo do rumo daquele registro. Na curva, esse retângulo invade o do registro anterior por dentro, numa cunha de cerca de (W²/8) · tan δ, em que δ é a mudança de rumo entre registros. Por fora fica um vão igual sem desenho.
- Na John Deere o rumo registrado (Track) é suavizado, o que alarga o leque.
- Exemplo sintético, com W = 12 m, passo de 2 m e raio de 20 m: a cunha tem 1,8 m² por registro (7,5 % do retângulo). Nas faixas varridas, 0 m².
- Nas curvas das figuras C5, a área desenhada "duas vezes" é 9,3 % no T30 e 11,3 % no T19. Nas faixas varridas é 0 m² nas duas.

**Faixas empilhadas no início.** Há uma parte desenho e uma parte real.
- *Parte desenho.* Na Case IH a distância D registrada é exatamente velocidade × duração, em 100 % dos registros. Já a posição do GPS cai em épocas de 0,2 s (5 Hz).
  - O passo do GPS dividido por D alterna entre cerca de 0,8, 1,0 e 1,2. Um passo longo vem logo depois de um curto em 85 % dos casos no T19 e em 97 % no T25.
  - Retângulos de comprimento D sobre passos desiguais se empilham.
  - Igualar D ao passo elimina 92,6 % (T19), 92,2 % (T25) e 75,5 % (T20) da sobreposição desenhada.
- *Parte real.* Nos registros 1 a 5 da Case IH, o chão foi cortado por outras passadas, numa mediana de 1.900 a 39.000 registros antes, ou seja, horas antes.
  - Só 2 a 15 % desse chão foi cortado nos 30 registros anteriores.
  - Entre 12 e 52 % foi cortado em outra sessão (dataset).
  - Portanto é a cabeceira colhida antes, não a manobra da própria passada.

**Rampa de cor.**
- Na John Deere não há sobreposição debaixo da rampa a partir do registro 2.
- Na Case IH a rampa continua depois que a sobreposição acaba. No T20 a fração já cortada é 0,024 no registro 8, e a produtividade ainda fica em 0,75 a 0,91 da mediana da passada nos registros 8 a 15.
- "Vermelho → verde" descreve bem o T30 e a Case IH. No T22, T23 e T29 o registro 1 é um pico alto, seguido de uma queda nos registros 3 a 9:

| Ensaio | Registro 1 / mediana da passada [IC 95 %] |
|---|---|
| T22 | 1,53 [1,12; 1,74] |
| T23 | 1,20 [0,88; 1,51] |
| T29 | 1,47 [1,27; 1,76] |

**Qual deles é sobreposição real?** Só os primeiros 6 a 8 registros da Case IH no início da passada. A isso se soma, no interior do talhão, a sobreposição com passadas vizinhas mais antigas, que o F8 já trata. O leque não é sobreposição, e a rampa também não.

## 2. Como o OCCD trata cada um hoje

| Fenômeno | Tratamento atual | Problema |
|---|---|---|
| Leque na curva | Só existe no desenho (`yield_clean.swath_quads`, retângulo W × D para trás no rumo). Não muda nenhum número | A pegada do F8 tem a mesma forma, e por isso o F8 conta a cunha como "já colhido" (defeito 1 abaixo) |
| Faixas empilhadas (Case IH) | A parte real é removida pelo F8. A parte desenho continua nas figuras | — |
| Rampa | O F7 corta 4 registros no início e 2 no fim. O F8 tira a parte sobreposta | Sobra déficit depois da cascata: o primeiro registro mantido no fim da passada está em 0,70 a 0,95 do interior |

**F8 hoje.**
- Cada registro recebe Overlap_f, a fração da sua "pegada" que já estava cortada.
- A pegada é o retângulo da corda entre o ponto anterior da mesma passada e o atual. No primeiro ponto, é um retângulo para trás no rumo, com a distância registrada.
- As pegadas são queimadas em ordem de tempo num raster de 0,25 m, somando todas as máquinas, pelo método de Han et al. 1997 / Drummond et al. 1999.
- São removidos os registros acima de um limiar por campo, lido de uma dose-resposta com tolerância de 3 %.
- O F8 remove registros; não corrige a produtividade de ninguém.
- Limiares em 2026:

| T19 | T20 | T25 | T22 | T23 | T29 | T30 |
|---|---|---|---|---|---|---|
| 5 % | 5 % | 10 % | 15 % | 25 % | 10 % (reserva; o automático deu 1 %) | 5 % |

**Largura.**
- Usa a largura registrada pelo monitor.
- Na John Deere essa largura já vem estreitada pelo controle de seções sobre área colhida. A produtividade exportada é fluxo / (largura registrada × velocidade); a razão massa/área tem mediana 1,000.
- Na Case IH a largura é constante (35 ou 39 ft) e o Y_Offset é 0.

**Curvas fechadas.** Não há filtro próprio; o F4, o F6 e o F7 acabam removendo os registros com raio < W/2.

**Defeitos que os testes encontraram.**
1. **A pegada de corda do F8 conta como "já cortada" uma cunha do próprio registro anterior,** a mesma do leque. Só essa cunha causa 9 a 64 % das remoções do F8, conforme o campo e a orientação do raster.
2. **O F8 ignora o Y_Offset.** Na John Deere, a faixa estreitada fica no centro da plataforma, e não na posição real das seções ativas.
3. **O atraso de fluxo é aplicado tarde.** O motor mede o atraso, mas só o aplica à geometria de saída, depois do F7 e do F8. No T29 foi aplicado com sinal oposto ao que as pontas de passada indicam (−5 contra +5 registros).
4. **O raster de 0,25 m é grosso demais para os limiares.**
   - Uma coluna do raster equivale a 1,7 a 2,3 % de W, então um limiar de 5 % decide entre 2 e 3 colunas.
   - Deslocar a origem do raster em 0,125 m muda 59 a 73 % das decisões do F8 no T19.
5. **A ordem de colheita é inferida** (início do dataset, depois Obj__Id), porque o campo Time do export do SMS só tem a data.

## 3. Os testes

Apresento na ordem das perguntas:
- **C (geometria):** é sobreposição?
- **A (viés):** a sobreposição baixa a produtividade, e corrigir pela largura efetiva funciona?
- **B (rampa):** a rampa depende do tempo ou da distância?

Vereditos possíveis, pela regra pré-registrada: **sustentada**, **refutada** ou **inconclusiva**.

### 3.1 Teste C: geometria do mapa

**Hipóteses pré-registradas.** ρ = 2R/W, em que R é o raio da curva.
- **H1 (teorema).** Com ρ ≥ 1, a área varrida, contada uma vez, é exatamente W × passo. Com ρ < 1, o chão novo é (1 + ρ)²/(4ρ) de W × passo.
- **H2.** Faixas varridas consecutivas não se sobrepõem quando as linhas da barra não se cruzam.
- **H2b.** A pegada do F8 (retângulo da corda) acrescenta uma cunha de (W²/8) · tan|Δβ|, em que Δβ é a mudança de direção da corda. Regra: mudar a pegada se a cunha sozinha causar ≥ 1 % das remoções do F8 ou atingir ≥ 0,1 % dos registros.
- **H3.** A sobreposição de cada retângulo desenhado com o anterior é (D − passo)⁺ · W + (W²/8) · tan|δ|, dentro de 0,9 a 1,1 do medido.
- **H4.**
  - John Deere: D = passo do GPS em ≥ 99 % dos registros, dentro de 1 %.
  - Case IH: D = velocidade × duração, e a dispersão do passo é ruído de tempo do GPS. Três critérios: autocorrelação lag-1 < −0,2; dispersão que cai com o número de registros (inclinação log-log ≤ −0,75); escala por passada dentro de 1 ± 0,03.
- **H5.** Curvas com ρ < 1 são menos de 2 % dos registros (limite superior do IC), e ≥ 80 % delas já saem no F0–F7.
- **H6.** A partir do registro 5, a fração da faixa sobre chão já cortado é ≤ 5 %.

**H1: sustentada.**
- Confirmada analiticamente e em curvas sintéticas (erro < 2 × 10⁻⁷). O revisor refez a dedução.
- Em curvas comuns (ρ ≥ 1), W × D é a área verdadeira. O resíduo de corda contra arco, cos(δ/2), fica abaixo de 0,1 % para mudança de rumo menor que 5° por registro.
- Com ρ < 1, W × D pode errar para os dois lados: para menos num pivô contínuo, para mais numa curva em S que dobra sobre si.

**H2: refutada como registrada; a condição corrigida vale.**
- Houve pares com sobreposição: T19 23, T20 4, T25 37, T22 28, T23 64, T29 55, T30 12. Quase todos tinham um passo para trás ou um salto de GPS, e já tinham saído no F0–F7.
- A condição corrigida exige duas coisas: as linhas da barra não se cruzam, e as duas pontas da barra andam para a frente. Com ela, de 372.435 pares, todos dão 0 m², exceto 2 (seção colapsando e rumo saltando 51°), já removidos pelo F1.
- Área da faixa / (W × passo): mediana 1,0000.

**H2b: sustentada.**
- O recálculo independente reproduz exatamente o Overlap_f do motor nos 7 ensaios (diferença máxima 0).
- Remoções do F8 causadas só pela cunha do registro anterior (números do revisor, no quadro do raster do motor):

| Ensaio | Registros removidos só pela cunha | % das remoções do F8 [IC 95 %] | Produtividade desses registros / mediana da passada [IC 95 %] |
|---|---|---|---|
| T19 | 2.091 | 55,7 [42,3; 70,4] | 1,00 |
| T20 | 287 | 9,4 [3,8; 21,9] | 0,94 [0,87; 1,00] |
| T25 | 931 | 31,2 [22,7; 42,3] | 1,00 |
| T22 | 242 | 40,3 [21,6; 60,2] | 1,01 |
| T23 | 122 | 14,2 [7,6; 26,4] | 1,00 |
| T29 | 2.923 | 40,9 [35,1; 46,6] | 0,95 [0,91; 0,97] |
| T30 | 656 | 31,6 [18,8; 55,7] | 0,96 [0,92; 1,00] |

- Num raster alinhado ao norte verdadeiro, a fração vai de 13 a 64 %. A faixa honesta, juntando os dois quadros, é 9 a 64 %.
- Todos os ensaios passam dos dois limites da regra.
- Em 6 de 7 ensaios esses registros rendem o mesmo que a mediana da passada; só no T29 o IC exclui 1. Isso é coerente com "não houve colheita dupla", mas é evidência de apoio, não prova.

**H3: refutada como quantificada; a atribuição qualitativa vale.**

| Ensaio | Sobreposição desenhada (% da área desenhada) | Registros com > 10 % |
|---|---|---|
| T19 | 8,8 [7,8; 10,0] | 40,1 % |
| T25 | 9,1 [8,7; 9,5] | 42,6 % |
| T20 | 0,68 | 0,40 % |
| T22 | 0,38 | 0,59 % |
| T23 | 0,34 | 0,48 % |
| T29 | 1,37 | 1,93 % |
| T30 | 0,37 | 0,17 % |

- A fórmula fica dentro de 0,9 a 1,1 só no T19, T25 e T29. Nos outros quatro ela superestima em 11 a 17 %.
- A origem da sobreposição desenhada fica clara:
  - Case IH: a maior parte vem de D ≠ passo. Igualar D ao passo remove 92,6 % no T19, 92,2 % no T25 e 75,5 % no T20.
  - John Deere: quase tudo vem da mudança de rumo.

**H4: John Deere refutada por pouco; Case IH sustentada no T19 e T25, inconclusiva no T20.**
- *John Deere.* D é o passo do GPS: de 5 a 95 % dos registros, passo/D fica entre 0,998 e 1,002; por passada, entre 1,0000 e 1,0006. Mas só 98,35 a 98,89 % dos registros ficam dentro de 1 %, abaixo dos 99 % registrados. O resto são registros curtos e saltos de GPS.
- *Case IH.* D = velocidade × duração em 100 % dos registros. O ruído de tempo do GPS fica confirmado:

| Ensaio | Autocorrelação lag-1 | Inclinação da dispersão | Veredito |
|---|---|---|---|
| T19 | −0,87 [−0,89; −0,84] (−0,59 pelo revisor, nos registros vivos depois do F7) | −0,99 | Sustentada |
| T25 | −0,92 | −1,02 | Sustentada |
| T20 | −0,22 (passa) | −0,58 (falha) | Inconclusiva (caso misto, fora da tabela de decisão) |

- **Achado útil para o nível de produtividade.** Na escala por passada, passo/D fica em 1,012–1,017 no T19 e 0,983–0,985 no T25: dentro de ± 3 %, mas significativamente diferente de 1. Se a distância do GPS for a verdadeira, o T19 está cerca de 1,2 a 1,7 % alto e o T25 cerca de 1,5 a 1,7 % baixo.

**H5: sustentada, exceto no T29.**

| | T19 | T20 | T25 | T22 | T23 | T29 | T30 |
|---|---|---|---|---|---|---|---|
| Registros com ρ < 1 dentro da passada | 2 | 5 | 6 | 1 | 2 | 16 | 0 |
| Removidos pelo F0–F7 | 100 % | 80 % | 83 % | 100 % | 100 % | 50 % [27; 100] | — |

- Os registros com ρ < 1 são 0,002 a 0,020 % do total, com limite superior do IC ≤ 0,04 %.
- No T29 só 50 % saem no F0–F7, abaixo dos 80 % registrados. Com n = 16, o teste tinha pouco poder.
- Com a curvatura medida pelo Track, nenhum desses registros chega ao mapa final. Medindo pela direção das cordas, 36 registros mantidos ficam abaixo de ρ = 1 (T22 3, T23 25, T29 8), o que é ≤ 0,04 % dos mantidos.
- O "1,4 %" da sondagem inicial no T19 eram 2 de 147 registros com mudança de rumo ≥ 5°: os mesmos 2 registros, com outro denominador.

**H6: sustentada na John Deere, refutada na Case IH.**

| Ensaio | Fração da faixa já cortada |
|---|---|
| T22, T23, T30 (JD) | 0 a partir do registro 2 |
| T29 (JD) | 0,10 no registro 2; 0,02 no registro 3 |
| T19 (Case IH) | 1,00 até o registro 2; 0,65 no 5; 0,056 no 9 |
| T20 (Case IH) | 1,00 até o registro 5; 0,024 no 8 |
| T25 (Case IH) | 0,47 no registro 5; 0,036 no 7 |

A sobreposição no início das passadas Case IH é real por 6 a 8 registros. Isso vale supondo que a ordem de colheita inferida esteja certa e que a antena não esteja deslocada para trás ou para a frente da plataforma.

**Teste a mais do revisor: a largura efetiva.** Espaçamento mediano entre passadas paralelas vizinhas, dividido pelo W registrado [IC 95 %]:

| T19 | T20 | T25 | T22 | T23 | T29 | T30 |
|---|---|---|---|---|---|---|
| 0,992 [0,976; 1,022] | 0,998 [0,982; 1,017] | 0,995 [0,987; 0,999] | 0,9993 [0,9988; 0,9996] | 0,9996 [0,9994; 0,9998] | 0,996 [0,991; 0,998] | 0,9992 [0,9987; 0,9995] |

A largura registrada é a base de área certa, com erro de até 0,8 %. Não há "largura nova" para calcular.

**Exploratório (teste C e revisão).**
- **O F8 é muito sensível ao raster.** Deslocar a origem 0,125 m, sem girar, muda esta fração das decisões:

| T19 (limiar 5 %) | T25 | T22 | T30 | T20 | T29 | T23 |
|---|---|---|---|---|---|---|
| 59–73 % | 14–41 % | 14–19 % | 16–19 % | 8–11 % | 9–12 % | 4–5 % |

  - O total removido muda no máximo 1,5 %, então é ruído em *quais* registros saem.
  - A causa é a cunha rasterizada. Excluindo o registro anterior, ou usando a faixa varrida, o ruído cai 36 a 98 %. A faixa varrida ainda deixa 2 a 16 % das decisões dependentes do raster.
- **O Overlap_f se acumula em 2 a 2,5 %**, exatamente uma coluna do raster: 12.622 registros no T20, ou 19 % dos vivos depois do F7.
- **O Track da John Deere é um rumo suavizado, não um atraso puro.** Um ajuste de atraso puro dá 1,8 a 3,2 registros, mas o pico da correlação cruzada fica em só 0,75 a 0,90 registro, e sobra um erro de 3,0 a 4,7°. Na Case IH o Track é praticamente o rumo instantâneo.

**Veredito do teste C.**
- O leque é desenho (H1 e H2 corrigida sustentadas).
- O empilhamento na Case IH é parte desenho e parte sobreposição real (H3 na forma qualitativa, H4, H6).
- A pegada do F8 deve mudar (H2b sustentada).
- Nenhum registro mantido precisa de correção de curva (H5).

### 3.2 Teste A: a sobreposição baixa a produtividade? Corrigir pela largura efetiva funciona?

**Desenho pré-registrado.**
- Modelo: razão = a(1 − b · f). A razão é a produtividade do registro dividida pela mediana dos controles: registros sem sobreposição (f = 0) da mesma máquina, de outra passada, a até 15 m (mínimo de 5 controles).
- População: registros que sobreviveram ao F0–F7, com pelo menos 15 registros antes e 15 depois na passada.
- Hipóteses:
  - **H0:** b = 0. A sobreposição não altera a produtividade registrada.
  - **H1:** b = 1. A produtividade cai na proporção da área sobreposta. É o pressuposto da correção pela largura efetiva, y/(1 − f).
  - **H2:** 0 < b < 1.
- Previsões:
  - **P1:** a Case IH segue H1.
  - **P2a:** a John Deere segue H0, porque o monitor já estreita a largura.
  - **P2b:** o estreitamento registrado na John Deere acompanha f com inclinação 1.
  - **P3:** o placebo (f = 0 contra f = 0) fica entre 0,98 e 1,02.
  - **P4:** erros em f puxam b para 0; logo, o subconjunto em que f é estável deve dar b maior.
- Regra sobre o IC 95 % de b:

| Se o IC de b... | Veredito |
|---|---|
| inclui 1 e exclui 0 | H1 |
| inclui 0 e exclui 1 | H0 |
| fica todo dentro de (0, 1) | H2 |
| inclui 0 e 1 | Inconclusivo |

- Checagem da correção: a curva corrigida por y/(1 − f) conta como "plana" se o IC de toda faixa de f toca o intervalo 0,97–1,03.

**Resultados pré-registrados (o revisor reproduziu todos).**

| Ensaio | b [IC 95 %] | Pela regra |
|---|---|---|
| T19 (Case IH) | 0,88 [0,61; 1,02] | H1 |
| T20 (Case IH) | 0,51 [0,13; 0,72] | H2 |
| T25 (Case IH) | 0,56 [0,39; 0,92] | H2 |
| **Case IH conjunto** | **0,66 [0,46; 0,85]** | **H2** |
| T22 (JD) | 0,08 [−0,77; 0,51] | H0 |
| T23 (JD) | 0,02 [−0,67; 0,43] | H0 |
| T29 (JD; raio de 22,9 m, desvio declarado) | −0,13 [−0,56; 0,44] | H0 |
| T30 (JD) | −0,17 [−0,49; 0,58] | H0 |
| **John Deere conjunto** | **−0,11 [−0,40; 0,38]** | **H0** |

**Curva da Case IH por faixa de sobreposição.** Razão normalizada pelo placebo [IC 95 %], ao lado do que H1 prevê:

| Faixa de f | Razão [IC 95 %] | H1 prevê |
|---|---|---|
| 0–2 % | 1,006 [0,997; 1,018] | 0,987 |
| 2–5 % | 0,999 [0,986; 1,015] | 0,974 |
| 5–10 % | 0,980 [0,965; 0,997] | 0,937 |
| 10–15 % | 0,981 [0,952; 1,013] | 0,886 |
| 15–25 % | 0,911 [0,793; 0,947] | 0,764 |
| 25–35 % | 0,931 [0,748; 0,965] | — |
| 35–50 % | 0,687 [0,576; 0,746] | 0,562 |
| 50–75 % | 0,615 [0,347; 0,764] | 0,287 |
| > 75 % | 0,324 [0,130; 0,566] | 0,226 |

A faixa acima de 75 % tem 297 registros de só 9 passadas; 226 deles vêm de 2 passadas do T19. Não há dados perto de f = 1, então não dá para falar em "piso".

**Correção y/(1 − f).**
- Case IH: 1,051 [1,033; 1,068] com 5–10 %; 1,114 [1,074; 1,156] com 10–15 %; cerca de 1,23 com 35–50 %; cerca de 1,5 acima de 50 %. A curva corrigida **não fica plana**, e isso é robusto.
- Que ela passe do ponto acima de 35 % depende da semente do bootstrap: em 20 sementes, o limite inferior variou de 1,023 a 1,051 e passou de 1,03 em só 55 % delas.
- John Deere: 2,0 com 35–50 % e 19,5 acima de 75 %, por causa de larguras registradas muito estreitas.

**O que o revisor mostrou, e que muda a leitura.**

*Case IH: H0 rejeitada de forma robusta.* Em todas as variantes de controle e de dose, o b conjunto fica entre 0,62 e 0,76, com limite inferior entre 0,36 e 0,46:

| Variante | b [IC 95 %] |
|---|---|
| Controles na mesma distância da borda | 0,622 [0,375; 0,904] |
| Só registros a ≥ 40 m da borda | 0,758 [0,362; 0,962] |
| Controles do mesmo dia | 0,616 [0,419; 0,893] |
| Só sobreposição de outras passadas | 0,672 [0,451; 0,877] |

*Case IH: H1 contra H2 não está resolvido.*
- **Poucas passadas carregam o resultado:**
  - T19: 6 passadas com f > 15 %; as 3 maiores têm 89 % desses registros.
  - T20: 4 passadas; as 3 maiores têm 99,6 %.
  - T25: a passada 14 sozinha tem 34 % dos registros com f > 15 %. É fisicamente implausível: sobreposição de 0,69 a 0,74 sobre chão colhido na noite anterior, com razão 0,89. Sem ela, o b do T25 sobe de 0,557 para 0,844.
- **Jackknife por passada** (b ± 2 erros-padrão): T25 [−0,03; 1,14], T20 [0,12; 0,89], Case IH conjunto [0,41; 0,91].
- **Mesma sessão contra outra sessão** (exploratório):
  - Sobreposição dentro da mesma sessão: b = 0,79 [0,45; 1,22], ou seja, H1.
  - Sobreposição sobre chão de outra sessão: b = 0,685 [0,40; 0,92], ou seja, H2.
  - A diferença entre as duas não é significativa.
  - As sobreposições entre sessões são bem mais largas: medianas de 0,56, 2,62 e 0,71 m (T19, T20, T25), contra 0,25 a 0,28 m dentro da sessão. Com f pequeno, elas dão razão acima de 1. É o sinal de um deslocamento do GPS entre sessões, que mede f errado para a passada inteira.
- **b muda com a faixa de f:** 0,27 [−0,06; 0,56] para f ≤ 15 %; 0,28 [0,17; 0,59] para f ≤ 35 %; 0,53 para f ≤ 50 %; 0,66 no total. Um b único não descreve os dados.

*John Deere: H0 não está estabelecida na faixa em que o F8 age.*
- **O H0 conjunto é um cancelamento.** Há déficit com 5 a 35 % de sobreposição (razão 0,83 a 0,93) e excesso acima de 35 % (1,53 [1,19; 1,63] acima de 75 %, larguras registradas muito estreitas). No ajuste linear, um anula o outro.
- **Restrito a f ≤ 35 %, a regra dá H2:** b = 0,486 [0,042; 0,724] com o Overlap_f do motor e 0,594 [0,378; 0,774] com a plataforma cheia.
- **O estimador robusto pré-registrado (b_med), que o relatório não mostrou,** dá −0,346 [−0,459; −0,045] no conjunto (fora das três hipóteses) e 0,543 [0,123; 0,770] no subconjunto estável.
- **Mas há um fator de confusão, a borda.** Os registros com 5 a 25 % de sobreposição ficam 6 a 14 m mais perto da borda que os controles. Com controles na mesma distância da borda (± 4 m), as faixas de 5 a 15 % viram 1,007 e 1,004. Isso, porém, se apoia em só 22 a 28 registros de 2 a 12 passadas.

*P2b.* As inclinações excluem 1, embora a correlação seja alta (r = 0,83 a 0,85). O estreitamento acompanha a sobreposição, mas menos que um para um. O T29 dá 0,45 e 0,53.

| T22 | T23 | T30 |
|---|---|---|
| 0,72 [0,42; 0,87] | 0,745 [0,55; 0,90] | 0,81 [0,44; 0,97] |

*P3 (placebo): passa no interior, mas não perto da borda, que é justamente onde está a dose.*
- Registros com f = 0 contra controles com f = 0: 0,78 no T19 a 0–15 m da borda; 1,23 no T19 a 15–30 m; 1,15 no T25 a 0–15 m; 0,93 no T25 a 15–30 m; 0,90 no T30 a 15–30 m.
- Os registros com f > 5 % ficam a uma mediana de 9 a 32 m da borda; os com f = 0, a 60 a 160 m.
- No T19 o IC do placebo é [0,898; 1,148], largo demais para detectar alguma coisa.
- Consequência para o motor: a dose-resposta do próprio F8 compara faixas sobrepostas perto da borda com a faixa f = 0 do campo inteiro, e herda essa confusão.

*P4.*
- Case IH: não sustentada, porque o subconjunto estável não sobe b. Só que esse subconjunto só elimina o ruído dentro da passada, não o deslocamento do GPS entre sessões.
- John Deere: sustentada. O subconjunto estável sobe b nos três ensaios: T22 de 0,08 para 0,31, T23 de 0,02 para 0,19, T30 de −0,17 para 0,60.

*"Sem viés detectável abaixo de 5 %" é falso.*
- John Deere, 2–5 %: +2,5 % [1,011; 1,037].
- Case IH, 5–10 %: −2,0 % [0,964; 0,997].
- Case IH, 2–5 %, com controles na mesma distância da borda: 0,981 [0,968; 0,993].

O piso de 5 % continua defensável, mas pela resolução, não pela ausência de viés. Um erro de posição de 0,3 a 1 m equivale a f de 2,0 a 9,4 % numa plataforma de 10,7 a 15,2 m. Entre os registros interiores, 46 a 73 % têm 0 < f ≤ 5 %; incluindo f = 0, são 79 a 96 %.

*Efeito na média, recalculado pelo revisor,* se os registros acima do limiar fossem mantidos:

| T19 | T20 | T25 | T22 | T23 | T29 | T30 |
|---|---|---|---|---|---|---|
| −2,0 % | −1,2 % | −1,2 % | +0,07 % | +0,49 % | −0,42 % | −0,76 % |

*Exploratório.* Em 37 a 80 % dos registros interiores com f > 0, todas as células sobrepostas foram cortadas pela própria passada: é a cunha do teste C. E 19,9 a 56,5 % das remoções do F8 não têm sobreposição de outra passada acima do limiar.

*Desvios do protocolo.* A regra que excluiu o T29 (menos de 300 registros com f > 0, ou menos de 30 passadas) não estava pré-registrada. O b_med e o P2c não foram reportados.

**Vereditos do teste A**

| Hipótese | Veredito |
|---|---|
| Case IH, H0: a sobreposição não baixa a produtividade | **Refutada** (robusto) |
| Case IH, H1 (queda proporcional à área, base da correção pela largura efetiva) contra H2 | **Inconclusiva.** O "P1 refutada" do relatório não se sustenta: o jackknife e a análise por sessão incluem 1 |
| A correção y/(1 − f) deixa a curva plana | **Refutada** (robusto em 5–15 %) |
| John Deere, H0 (P2a) | **Inconclusiva** em f ≤ 35 %. O H0 conjunto é cancelamento, um artefato da forma do modelo |
| P2b: o estreitamento da JD acompanha f com inclinação 1 | **Parcialmente sustentada** (correlação alta, inclinação < 1) |
| P3: placebo | **Sustentada no interior, refutada perto da borda** |
| P4: erros em f puxam b para 0 | Case IH **inconclusiva**; John Deere **sustentada** |

### 3.3 Teste B: a rampa depende do tempo ou da distância?

**Hipóteses pré-registradas.**
- **HT (tempo):** o déficit depende dos segundos desde o início, ou até o fim, da passada. É o enchimento e esvaziamento da colhedora mais o atraso do sensor.
- **HD (distância):** o déficit depende dos metros. Seria um efeito de borda do talhão.
- **HM:** os dois contribuem.
- **HO (sobreposição):** o déficit do início vem de faixa já colhida.

**Como foi testado.**
- *Tempo contra distância.* As passadas foram divididas em terços de velocidade. Se a causa for tempo, a rampa tem o mesmo comprimento em segundos nos três terços, e as passadas rápidas a esticam em metros. Se for distância, acontece o contrário. A decisão sai dos IC de log R_t (razão dos comprimentos em segundos entre o terço rápido e o lento) e log R_d (a mesma razão em metros).
- *Comprimento da rampa.* k97 é o primeiro registro a partir do qual a produtividade fica ≥ 0,97 do interior por 5 posições seguidas (0,97 é a tolerância de 3 % do F8). N = k97 − 1 é o número de registros a descartar. Uma regra fixa é "curta demais" se fica abaixo do limite inferior do IC de N.
- *HO.* Compara inícios limpos (Overlap_f < 0,05 nos registros 1 a 10) com inícios sobrepostos, pelo déficit médio nos registros 1 a 5 (D5).

**Pressupostos.**
- 1 registro = 1 s (vale para 96 a 99,8 % das linhas).
- O início de uma passada é uma entrada na cultura.
- A3: a classe de velocidade não está ligada ao que causa a rampa.
- O atraso de fluxo é constante.

**Tempo contra distância: inconclusivo.**
- Das 14 pontas (7 ensaios × início e fim): 2 HT (fim do T19 e fim do T29), 0 HD, 3 anômalas e 9 inconclusivas. O revisor reproduziu os 14 vereditos.
- O revisor também mostrou por que o desenho falhou: a classe de velocidade se confunde com dia de colheita, dataset e máquina.

| Ensaio | Confusão |
|---|---|
| T20 | 26 de 35 passadas lentas são de 24/9; 28 de 34 rápidas são de 25 e 26/9 |
| T22 | 27 de 30 passadas rápidas são de 17/9 |
| T25 | 22 de 35 lentas vêm de um dataset de 5/9; 25 de 38 rápidas, de um de 18/9 |
| T29 | A máquina 1 é a mais lenta e a máquina 3 a mais rápida |

- Além disso, na janela dos registros 21 a 30, as passadas rápidas rendem 0 a 8 % menos que o próprio interior. A diferença entre lentas e rápidas (2 a 22 %) é significativa em 5 de 7 ensaios.
- Isso quebra o pressuposto A3. "Os fins são HT" não se sustenta.

**Comprimento da rampa nas passadas brutas** (k97 [IC 95 %], em registros ≈ segundos):

| Ensaio | Início | Fim |
|---|---|---|
| T19 | 8 [6; 24] | 12 [8; 26] |
| T20 | 19 [15; 23] | 23 [17; 24] |
| T25 | 10 [7; 14] | 13 [11; 24] |
| T22 | 17 [1; 23] | 25 [16; 26] |
| T23 | 15 [13; 17] | 22 [15; 25] |
| T29 | 14 [10; 18] | 15 [12; 24] |
| T30 | 17 [10; 23] | 21 [8; 24] |

- **No fim, o F7 (2 registros) é curto demais em 7 de 7 ensaios.** As regras publicadas para o fim (Griffin, 2 a 4 s; Simbahan, 4 s; Ping & Dobermann, 6 s) também são curtas em 7 de 7.
- **No início, o F7 (4 registros) é curto demais de forma robusta em 5 de 7 ensaios.** No T29 está no limite: o limite inferior do IC varia de 1 a 10 conforme a semente, e P(N ≤ 4) = 0,022. No T22 os 4 registros são compatíveis.
- **O F7 fixo está refutado.**

**Sobreposição no início (HO).** Overlap_f médio:

| Ensaio | Registro 1 | Registro 5 | Registro 10 | Interior |
|---|---|---|---|---|
| T19 | 0,91 | 0,58 | 0,16 | 0,04 |
| T20 | 0,93 | 0,77 | 0,08 | 0,02 |
| T25 | 0,84 | 0,47 | 0,10 | 0,03 |
| T22 | 0,45 | 0,12 | 0,07 | 0,02 |
| T29 | 0,51 | 0,15 | 0,07 | 0,04 |
| T30 | 0,28 | 0,06 | 0,04 | 0,03 |

- Case IH: só 0 a 3 inícios limpos por ensaio, então a regra não consegue testar HO.
- T30: os inícios limpos (n = 41) ainda têm D5 = 0,42 [0,24; 0,65]. Nos 18 que vêm logo depois de uma meia-volta, 0,50 [0,21; 0,67]. **A sobreposição como causa única está refutada no T30.**
- T22: os inícios limpos (n = 10) têm sobra, não déficit (D5 = −0,13 [−0,32; −0,01]).

**Depois do F8.**
- O déficit do início some no T19 e no T25 (k97 = 1). No T20 sobram cerca de 8 registros, começando em 0,76 do interior.
- Na saída real do motor (depois de toda a cascata, incluindo F9 a F11 e F5b), o k97 fica assim:

| Ensaio | Início | Fim |
|---|---|---|
| T19 | não atingido na janela | 2 |
| T20 | 9 | 11 |
| T25 | 1 | 25 (instável) |
| T22 | 17 | 22 |
| T23 | 11 | 20 |
| T29 | 5 | 9 |
| T30 | 5 | 5 |

- O primeiro registro mantido no fim da passada fica em 0,70 a 0,95 do interior.

**Testes novos do revisor (pré-registrados, hash bf7822ea…6276).**
- **R3: início contra fim na mesma cabeceira.** Usa os registros mantidos depois do F8, pelos metros desde o primeiro ou até o último registro. Um efeito de borda do talhão não sabe para que lado a máquina ia, então prevê Δ = 0 (Δ = Q_início − Q_fim, as razões de produtividade medidas no início e no fim, na mesma faixa de distância).

| Ensaio | Δ a 0–5 m [IC 95 %] | Veredito |
|---|---|---|
| T20 | 0,48 [0,43; 0,53] | Borda como causa única refutada |
| T25 | 0,36 [0,24; 0,44] | Refutada |
| T22 | 0,18 [0,09; 0,23] | Refutada |
| T23 | 0,06 [0,004; 0,12] | Refutada |
| T29 | 0,25 [0,20; 0,31] | Refutada |
| T19 | 0,10 [−0,01; 0,19] | Não refutada |
| T30 | −0,03 [−0,14; 0,12] | Não refutada |

  O fim é mais fundo que o início no mesmo lugar, então a causa está na máquina.
- **R2: gradientes de borda existem.** Em registros longe das pontas da própria passada: T20 0,63 [0,59; 0,68] a 0–10 m da borda; T25 0,83 [0,74; 0,90] a 10–20 m. São produtividade real e devem ficar no mapa; só não explicam a rampa.

**Exploratório do revisor: aplicar o atraso de fluxo antes do F8.** Deslocar a produtividade s registros em relação às posições, e só depois aplicar o F8, reduz o déficit do fim (D5):

| Ensaio | D5 do fim sem deslocamento | Com o melhor deslocamento | Atraso medido pelo motor |
|---|---|---|---|
| T25 | 0,33 | 0,07 (s = +3) | +3 |
| T22 | 0,19 | 0,06 (+3) | +2 |
| T23 | 0,13 | 0,07 (+2) | +2 |
| T29 | 0,28 | 0,06 (+5) | −5 (sinal oposto) |

- No T19 o melhor deslocamento é +1 a +2 registros e o motor mede 0, ou seja, praticamente nenhum.
- No T20 e no T30 sobra um transiente simétrico (cerca de 0,3 e 0,15).
- Em 4 a 5 ensaios, boa parte da rampa do fim se comporta como um desalinhamento de 2 a 5 registros entre produtividade e posição. O motor mede esse desalinhamento, mas só o aplica à geometria de saída.

**Exploratório do revisor: a ideia da largura efetiva.**
- No interior das passadas, na faixa de 5 a 15 % de sobreposição, o IC de r/(1 − Overlap_f) fica inteiro acima de 1 nos 7 ensaios (1,03 a 1,18). A mediana da razão ali é 0,99 a 1,01, não os 0,85 a 0,95 que a correção supõe.
- Nos registros mantidos depois do F8, a correção mudaria o D5 em no máximo 0,02.

**A tabela de F7 por campo proposta pelo teste B não deve ser adotada como está.**
- Foi medida depois do F7 antigo. Na curva certa (F0–F6 + F8, sem F7), o início do T23 passa de 10 para 16, o início do T30 de 10 para 15, e o fim do T30 de 18 para 11.
- O k97 muda com a semente do bootstrap.
- O custo é alto para o ganho:

| | T22 | T23 | T29 | T30 | T20 | T19 | T25 |
|---|---|---|---|---|---|---|---|
| Registros mantidos hoje que seriam removidos | 9,9 % | 9,1 % | 8,0 % | 9,9 % | 2,3 % | 0,3 % | 0 % |

  A média do campo subiria só 0,2 a 0,7 % (por exemplo, T22 de 68,48 para 68,86 bu/ac; T30 de 59,36 para 59,77 bu/ac).

**Vereditos do teste B**

| Hipótese | Veredito |
|---|---|
| HT (tempo) | **Inconclusiva**: 2 de 14 pontas, e a velocidade está confundida com dia, dataset e máquina |
| HD (distância, borda do talhão) | **Inconclusiva** no teste de velocidade (0 de 14). **Refutada como causa única** da rampa pelo R3 em 5 de 7 ensaios |
| HM | **Inconclusiva** |
| HO (sobreposição) | **Refutada como causa única** no T30. Na Case IH a regra não consegue testá-la (quase não há inícios limpos), mas os registros 1 a 7–10 estão sobre chão já cortado (teste C, H6) e o déficit some depois do F8 no T19 e no T25 |
| O F7 fixo (4/2) basta | **Refutada**: fim curto em 7 de 7; início curto de forma robusta em 5 de 7 |

## 4. O que deveríamos fazer, por prioridade

### 1. Não implementar correção por "largura efetiva"

Isso vale para y/(1 − f), para uma largura nova e para o "scale per area" do SMS aplicado ao nosso f.

**Sustentado por:**
- A largura registrada está certa com erro de até 0,8 % (espaçamento/W de 0,992 a 0,9996; revisão C).
- A correção y/(1 − f) não deixa a curva plana: 1,051 [1,033; 1,068] com 5–10 % e 1,114 [1,074; 1,156] com 10–15 % (teste A).
- No interior, r/(1 − f) fica acima de 1 com 5–15 % nos 7 ensaios (revisão B).
- Na John Deere a largura registrada já vem estreitada dentro da produtividade exportada, e não há base para uma segunda correção (H0 da JD inconclusiva).
- O f não é confiável para a passada inteira entre sessões nem perto das bordas (revisão A).

**O que refutaria:**
- Um ensaio controlado com RTK, com passadas de sobreposição deliberada de 0, 25 e 50 % em cultura uniforme, ≥ 5 repetições, numa Case IH com largura cheia, em que o IC de b inclua 1 e a curva corrigida fique plana (todo IC tocando 0,97–1,03).
- Ou, num campo, um espaçamento entre passadas/W com IC fora de 0,98–1,02.

### 2. Manter o F8 como remoção, com limiar por campo e nunca abaixo de 5 %

O limiar continua vindo da dose-resposta de cada campo.

**Sustentado por:**
- A sobreposição baixa a produtividade na Case IH: H0 refutada, b entre 0,62 e 0,76, limite inferior entre 0,36 e 0,46 (teste A).
- Os primeiros 6 a 8 registros da Case IH são sobreposição real (teste C, H6), e o F8 limpa esses inícios no T19 e no T25 (teste B).
- O piso de 5 % vem da resolução: 0,3 a 1 m de erro de posição equivale a f de 2,0 a 9,4 %, e uma coluna do raster a 1,7 a 2,3 % de W.

**O que refutaria:**
- Um viés reprodutível abaixo de 5 %, com a sobreposição medida em vetor e posições RTK.
- Ou uma dose-resposta refeita (item 3) sem queda em nenhuma faixa de f.

### 3. Corrigir a geometria do F8 e refazer a dose-resposta, pré-registrada, por campo

**O que mudar:**
- a. A pegada passa a ser a faixa varrida entre linhas de barra consecutivas. A alternativa mais simples é excluir as células do registro imediatamente anterior (a regra R3 do `sms_swath.py`).
- b. Na John Deere, deslocar a faixa estreitada pelo Y_Offset.
- c. Fazer a dose-resposta contra controles locais na mesma distância da borda, e não contra a faixa f = 0 do campo inteiro.
- d. Marcar como de baixa confiança a sobreposição sobre chão de outra sessão.
- e. Quando o cartão bruto (.cn1/.jdl) existir, usar a hora de cada registro para a ordem de colheita.
- f. Antes de confiar em decisões individuais com limiar ≤ 10 %, medir a sobreposição em vetor ou num raster de 0,05 m ou mais fino.

**Sustentado por:**
- H2b: a cunha sozinha responde por 9 a 64 % das remoções, e esses registros rendem como a mediana da passada em 6 de 7 ensaios (teste C).
- 19,9 a 56,5 % das remoções não têm sobreposição de outra passada (teste A).
- A faixa varrida tira 36 a 98 % do ruído de raster (revisão C).
- O placebo falha perto da borda (revisão A).
- Na John Deere, |Y_Offset| > 1 ft em 7 a 30 % dos registros.

**Previsão verificável.** O Overlap_f médio em curva cai para perto do valor da faixa varrida: T19 de 15,0 para 7,6 %, T25 de 23,1 para 13,6 %, T22 de 12,9 para 3,5 %, T23 de 14,4 para 5,8 %, T29 de 12,2 para 5,1 %, T30 de 10,5 para 5,2 %.

**O que refutaria:**
- Na maioria dos campos, os registros que deixam de ser removidos rendem abaixo da mediana da passada, com IC excluindo 1. Nesse caso eram sobreposição real e a pegada antiga estava certa. Hoje isso só acontece no T29 (0,95 [0,91; 0,97]).
- Para o item b (previsão minha, ainda não testada): se o Y_Offset põe as seções ativas no lugar certo, a sobreposição da faixa estreitada e deslocada sobre chão já colhido deve cair para perto de zero nos registros em que o monitor fechou seções. Se continuar alta, o Y_Offset não descreve a posição das seções, e a correção deve ser revista.

### 4. Desenhar no mapa a faixa varrida, e não o retângulo W × D

**Como desenhar:**
- John Deere: direção da barra tirada das posições (rumo da corda centrada), porque o Track é suavizado.
- Primeiro registro da passada: retângulo para trás.
- Linhas de barra cruzadas: dois triângulos.

É só para exibição. Na Case IH a área W × passo difere da área W × D da produtividade em cerca de ± 20 % por registro, então nunca se deve somar massa sobre os polígonos desenhados. Com isso o leque e o empilhamento da própria passada desaparecem do mapa.

**Sustentado por:**
- H1 e H2 corrigida: as faixas se encaixam com 0 m² em 372.435 pares.
- H3: o leque é a cunha do desenho, e na Case IH D ≠ passo.

**O que refutaria:** num campo novo, faixas varridas consecutivas, com a máquina andando para a frente, ainda se sobrepondo acima do zero numérico.

### 5. Testar o atraso de fluxo antes do F7 e do F8, e conferir à mão o sinal do T29

A ideia é aplicar o deslocamento medido às posições antes do F7 e do F8, e não só à geometria de saída.

**Sustentado por:** o exploratório da revisão B. O D5 do fim cai de 0,33 para 0,07 no T25, de 0,19 para 0,06 no T22, de 0,13 para 0,07 no T23, e de 0,28 para 0,06 no T29, este com sinal oposto ao do motor. Por ser exploratório, primeiro é preciso confirmar a previsão que o revisor já registrou: no T22, T23 e T25, o D5 do fim depois do F8 cai para 0,10 ou menos. Depois, repetir em campos novos.

**O que refutaria:**
- Em campos novos, o D5 do fim não cai para ≤ 0,10 com o deslocamento medido.
- Ou o melhor deslocamento não coincide com o que o motor mede, como aconteceu no T29.

### 6. Só depois de 3 e 5: trocar o F7 fixo (4/2) por um N medido por campo e por ponta

**Como medir:**
- Na curva F0–F6 + F8, sem o F7 antigo.
- Com uma estatística estável à semente: o menor N com probabilidade bootstrap ≥ 0,9 de que a produtividade relativa no registro k (Q_k) fique ≥ 1 − tolerância para todo k > N.
- Reportando o IC e o custo em registros.

**A tolerância (3 % ou 10 %) é decisão de política, não de ciência, e deve ser declarada.**
- Com 10 %, os N conjuntos seriam: Case IH 0 no início e 6 no fim; John Deere 1 e 4.
- Com 3 %, a John Deere perde 8 a 10 % dos registros para subir a média 0,2 a 0,7 %.

**Sustentado por:** o F7 fixo está refutado (teste B), e a tabela atual é mal especificada e instável (revisão B).

**O que refutaria ou mudaria:**
- Se, depois do item 5, o k97 pós-F8 de um campo for 1, o F7 daquela ponta passa a 0.
- Se o ensaio controlado (item 7) mostrar HD, o F7 deve cortar metros em vez de registros.
- Se a queda rasa da John Deere aparecer nas mesmas cabeceiras em outros anos e culturas, ela é produtividade real e deve ficar no mapa (tolerância de 10 %).

### 7. Ensaio de campo controlado, para as duas perguntas que os dados observacionais não fecham

As perguntas são H1 contra H2 (teste A) e tempo contra distância (teste B).

**Desenho:**
- Faixas com RTK e sobreposição deliberada de 0, 25 e 50 % em cultura uniforme, com ≥ 5 repetições, numa Case IH com largura cheia.
- Velocidade definida pelo operador, com o controle automático desligado. Duas velocidades com pelo menos o dobro de diferença (por exemplo 2 e 4,5 mph), alternadas passada a passada no mesmo dia, com ≥ 20 entradas por velocidade em cultura em pé.
- Um teste de parada e arranque por colhedora, para medir diretamente o enchimento e o atraso.

**Previsões:**
- HT: o mesmo x90 (posição em que a curva ajustada atinge 90 % do interior) em segundos nas duas velocidades.
- HD: o mesmo x90 em metros.
- H1: o IC de b inclui 1 nas faixas deliberadas.

### 8. O que não fazer agora

- **Não criar filtro de borda por distância.** Os gradientes de borda do T20 e do T25 são produtividade real (R2), e a borda não explica a rampa (R3).
- **Não criar regra de largura mínima nem de "dupla contagem" na John Deere** antes de um teste pré-registrado com controles na mesma distância da borda e passadas suficientes (teste A e revisão).

### 9. Conferir a calibração de distância e velocidade do T19 e do T25

O passo do GPS/D por passada é 1,012–1,017 no T19 e 0,983–0,985 no T25, ou seja, um erro de nível de ± 1,2 a 1,7 % (revisão C).

**O que refutaria:** a distância do GPS estar errada e a do monitor certa (por exemplo, por deriva de posição). Confirmar pelo fechamento com o peso da balança, quando houver.

## 5. Limites

- **Os dados são observacionais.** A sobreposição e a velocidade não foram sorteadas, os controles são espaciais, e a velocidade acompanha dia, dataset, máquina e cultura. Por isso H1 contra H2 e tempo contra distância continuam em aberto.
- **A ordem de colheita é inferida,** porque o export do SMS não tem hora. Isso afeta sobretudo o T23 e o T29 (várias máquinas no mesmo dataset) e as sobreposições entre sessões.
- **Há poucas passadas nas sobreposições altas:** 4 a 6 passadas influentes na Case IH. O bootstrap percentil pode cobrir menos que 95 % e discorda do jackknife. Passadas vizinhas são acopladas pela sobreposição, então os IC são um pouco otimistas.
- **A borda do talhão confunde a análise.** Os registros sobrepostos ficam perto da borda, onde o placebo falha. A confusão não está resolvida para a John Deere e também atinge a dose-resposta do F8.
- **A posição tem limitações:**
  - o deslocamento longitudinal entre antena e plataforma é desconhecido e pode mover a rampa da Case IH em 2 a 3 registros;
  - o F8 ignora o Y_Offset;
  - sobreposições abaixo de cerca de 5 % ficam abaixo da resolução;
  - o raster de 0,25 m quantiza o Overlap_f.
- **"Coberto antes" não é "colhido antes".** Se a Case IH registra com a plataforma levantada na manobra, parte da sobreposição do início seria chão apenas percorrido.
- **O k97 é mal condicionado:** muda com a semente do bootstrap e com 0,3 % de mudança na referência.
- **Vários resultados são exploratórios e precisam de confirmação pré-registrada:** o atraso aplicado antes do F8, as épocas de 0,2 s, o Track suavizado, a sensibilidade ao raster, a largura efetiva no interior e a comparação entre mesma sessão e outra sessão.
- **O escopo é estreito:** uma safra (2026), 7 campos de cereais e 2 famílias de monitor (Case IH e John Deere GreenStar 4).

## Figuras de apoio

Os caminhos abaixo são relativos à pasta de trabalho dos testes (`overlap_tests/`); essas figuras e pastas não acompanham o app. As figuras da avaliação da v2.4 estão em `figs/` ao lado deste arquivo (ver `README.md`).

Na geometria (o que a imagem mostra):
- `overlap_tests/testC_geometry/fig/C5_T19_turn_and_pass_start_three_ways.png`: curva e início de passada no T19, desenhados de três formas.
- `overlap_tests/testC_geometry/fig/C5_T30_turn_and_pass_start_three_ways.png`: o mesmo no T30.
- `overlap_tests/testC_geometry/fig/C1_synthetic_theorem.png`: o teorema da faixa varrida (H1).
- `overlap_tests/testC_geometry/fig/C4_pass_start_geometry_vs_ramp.png`: geometria do início da passada contra a rampa.
- `overlap_tests/testC_review/fig/R4_pass_spacing_vs_W.png`: largura efetiva medida (espaçamento/W).
- `overlap_tests/testC_review/fig/R1_raster_frame_flips.png`: sensibilidade do F8 ao raster.

No viés da sobreposição:
- `overlap_tests/testA_bias/fig/fig1_ratio_vs_overlap_engine.png`: razão de produtividade contra sobreposição.
- `overlap_tests/testA_bias/fig/fig3_after_correction.png`: a curva depois da correção y/(1 − f).
- `overlap_tests/testA_review/fig/rv2_b_forest_variants.png`: b em todas as variantes de controle e de dose.
- `overlap_tests/testA_review/fig/rv3_edge_placebo.png`: placebo perto da borda.

Na rampa:
- `overlap_tests/testB_time_vs_distance/figs/fig3_ramp_length.png`: comprimento da rampa por ensaio.
- `overlap_tests/testB_time_vs_distance/figs/fig4_overlap_at_starts.png`: sobreposição nos inícios de passada.
- `overlap_tests/review_testB/figs/R3_same_headland_start_vs_end.png`: início contra fim na mesma cabeceira (R3).
- `overlap_tests/review_testB/figs/X3_delay_before_F8.png`: atraso de fluxo aplicado antes do F8.
- `overlap_tests/review_testB/figs/X8_swath_model_test.png`: teste do modelo de largura efetiva.

Pastas com os protocolos, scripts e resultados de cada teste e de cada revisão:
- `overlap_tests/testA_bias`
- `overlap_tests/testA_review`
- `overlap_tests/testB_time_vs_distance`
- `overlap_tests/review_testB`
- `overlap_tests/testC_geometry`
- `overlap_tests/testC_review`
