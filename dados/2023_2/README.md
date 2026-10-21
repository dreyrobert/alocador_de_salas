# Horários de 2023_2

`horarios_2023_2.xlsx` foi padronizado a partir das 440 linhas de
`horarios_2023_2_original.xlsx`, preservado sem alterações.

- Código, nome, curso, fase e horários foram extraídos da descrição textual.
- A ordem dos registros e os horários com suas datas foram preservados.
- O nome mantém qualificadores presentes na origem, como `(GRADUAÇÃO)`.
- Nas nove fusões, cursos e fases correspondentes são separados por `;`.
- Optativas e turmas sem período numérico informado usam fase `0` (41
  registros). Isso evita agrupamento por fase no leitor atual. Os qualificadores
  `ESPECIAL TODOS OS CURSOS`, `PIN` e `PROIMIGRANTE` foram preservados no campo
  `curso`; fase `0` nesses casos indica período não informado, não comprova
  que a turma seja optativa.
- `ch_ccr` permanece em branco porque a carga horária não está explícita na
  origem. O modelo não usa esse campo nas restrições nem no objetivo.
- A coluna `vagas` continua ausente. O leitor assume 25 alunos por turma
  quando essa informação não é fornecida, conforme a hipótese histórica.

O número original de turma e a anotação isolada “AULAS VESPERTINAS EM SALA
DISTINTA” permanecem disponíveis no arquivo original. O leitor atual gera sua
própria numeração de turmas e não interpreta essa anotação.
